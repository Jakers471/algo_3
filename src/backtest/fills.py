"""Resolve orders against a single bar into fill prices - the fill model.

One job (pure, swappable): given an order and a bar's OHLC, decide IF and at
WHAT price it fills. No loop, no state. This is where the backtest is honest
or not, so the assumptions are explicit and conservative:

- Bars carry no bid/ask (audit: fills_no_quotes) -> model >=1 tick of adverse
  slippage on stop fills (a triggered stop becomes a market order).
- Gap-through: if a bar OPENS beyond a stop trigger, it fills at the OPEN
  (worse), not the trigger.
- Take-profit is a resting limit: fills at the target price exactly (no
  favorable-gap benefit, no slippage) - the conservative side.
- Ambiguous bar: if one bar's range spans BOTH the stop and the target, we
  cannot know the intrabar path, so we assume the STOP filled first
  (adverse-first) and FLAG the result as ambiguous.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.backtest.bracket import Bracket, Direction


@dataclass(frozen=True)
class Bar:
    """The four prices a fill decision needs (a row of the bars frame)."""

    open: float
    high: float
    low: float
    close: float


@dataclass(frozen=True)
class ExitFill:
    price: float
    reason: str          # "stop" | "target"
    ambiguous: bool      # True when the same bar hit both stop and target


def entry_fill(bracket: Bracket, bar: Bar, tick_size: float, slip_ticks: int) -> float | None:
    """Resolve a resting stop entry against a bar. Returns the fill price or None.

    Adverse slippage is applied because a triggered stop fills as a market order.
    """
    slip = slip_ticks * tick_size
    if bracket.direction is Direction.LONG:  # buy-stop above price
        if bar.high >= bracket.entry_stop:
            base = bar.open if bar.open >= bracket.entry_stop else bracket.entry_stop
            return base + slip
        return None
    # SHORT: sell-stop below price
    if bar.low <= bracket.entry_stop:
        base = bar.open if bar.open <= bracket.entry_stop else bracket.entry_stop
        return base - slip
    return None


def exit_fill(
    direction: Direction,
    stop_price: float,
    target_price: float,
    bar: Bar,
    tick_size: float,
    slip_ticks: int,
) -> ExitFill | None:
    """Resolve an open bracket's stop-loss / take-profit against a bar.

    Adverse-first on ambiguity: if both are touched, the stop is taken and
    ``ambiguous`` is set so the caller can flag/count the uncertain outcome.
    """
    slip = slip_ticks * tick_size
    if direction is Direction.LONG:
        hit_stop = bar.low <= stop_price      # sell-stop below entry
        hit_target = bar.high >= target_price  # sell-limit above entry
        if hit_stop:
            base = bar.open if bar.open <= stop_price else stop_price  # gap-down fills worse
            return ExitFill(base - slip, "stop", ambiguous=hit_target)
        if hit_target:
            return ExitFill(target_price, "target", ambiguous=False)
        return None
    # SHORT: stop above entry, target below
    hit_stop = bar.high >= stop_price
    hit_target = bar.low <= target_price
    if hit_stop:
        base = bar.open if bar.open >= stop_price else stop_price
        return ExitFill(base + slip, "stop", ambiguous=hit_target)
    if hit_target:
        return ExitFill(target_price, "target", ambiguous=False)
    return None
