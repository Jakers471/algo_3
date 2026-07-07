"""Lock the fill model's honest assumptions - the subtle, result-critical logic.

Every backtest and walk-forward rides on fills.py, so its behavior is pinned
here: adverse slippage on stops, gap-through fills at the open, take-profit at
the limit, and adverse-first (stop) on an ambiguous same-bar stop+target.
"""

from pytest import approx

from src.backtest.fills import Bar, entry_fill, exit_fill
from src.strategy.bracket import Bracket, Direction

TICK = 0.25
SLIP = 1          # ticks
SLIP_AMT = 0.25   # TICK * SLIP


# --- entry: resting stop orders ------------------------------------------

def test_long_entry_fills_at_trigger_plus_slippage():
    b = Bracket(Direction.LONG, entry_stop=100.0, stop_price=95.0, target_price=110.0)
    bar = Bar(open=99.0, high=101.0, low=98.0, close=100.0)
    assert entry_fill(b, bar, TICK, SLIP) == approx(100.0 + SLIP_AMT)


def test_long_entry_gap_through_fills_at_open():
    b = Bracket(Direction.LONG, entry_stop=100.0, stop_price=95.0, target_price=110.0)
    bar = Bar(open=100.5, high=101.0, low=100.3, close=100.8)  # opened above trigger
    assert entry_fill(b, bar, TICK, SLIP) == approx(100.5 + SLIP_AMT)


def test_long_entry_not_triggered_returns_none():
    b = Bracket(Direction.LONG, entry_stop=100.0, stop_price=95.0, target_price=110.0)
    bar = Bar(open=98.0, high=99.5, low=97.0, close=99.0)
    assert entry_fill(b, bar, TICK, SLIP) is None


def test_short_entry_fills_at_trigger_minus_slippage():
    b = Bracket(Direction.SHORT, entry_stop=100.0, stop_price=95.0, target_price=110.0)
    bar = Bar(open=101.0, high=102.0, low=99.0, close=100.0)
    assert entry_fill(b, bar, TICK, SLIP) == approx(100.0 - SLIP_AMT)


def test_short_entry_gap_through_fills_at_open():
    b = Bracket(Direction.SHORT, entry_stop=100.0, stop_price=95.0, target_price=110.0)
    bar = Bar(open=99.5, high=99.8, low=99.0, close=99.2)  # opened below trigger
    assert entry_fill(b, bar, TICK, SLIP) == approx(99.5 - SLIP_AMT)


# --- exit: LONG stop-loss / take-profit ----------------------------------

def test_long_stop_fills_at_stop_minus_slippage():
    ex = exit_fill(Direction.LONG, stop_price=95.0, target_price=110.0,
                   bar=Bar(98.0, 99.0, 94.0, 96.0), tick_size=TICK, slip_ticks=SLIP)
    assert ex.reason == "stop"
    assert ex.ambiguous is False
    assert ex.price == approx(95.0 - SLIP_AMT)


def test_long_stop_gap_down_fills_at_open():
    ex = exit_fill(Direction.LONG, stop_price=95.0, target_price=110.0,
                   bar=Bar(93.0, 94.0, 92.0, 93.0), tick_size=TICK, slip_ticks=SLIP)
    assert ex.reason == "stop"
    assert ex.price == approx(93.0 - SLIP_AMT)  # gapped below the stop


def test_long_target_fills_at_limit_no_slippage():
    ex = exit_fill(Direction.LONG, stop_price=95.0, target_price=110.0,
                   bar=Bar(105.0, 111.0, 104.0, 110.0), tick_size=TICK, slip_ticks=SLIP)
    assert ex.reason == "target"
    assert ex.ambiguous is False
    assert ex.price == approx(110.0)


def test_long_ambiguous_bar_takes_stop_and_flags():
    ex = exit_fill(Direction.LONG, stop_price=95.0, target_price=110.0,
                   bar=Bar(100.0, 111.0, 94.0, 105.0), tick_size=TICK, slip_ticks=SLIP)
    assert ex.reason == "stop"          # adverse-first
    assert ex.ambiguous is True          # both were touched
    assert ex.price == approx(95.0 - SLIP_AMT)


def test_long_no_exit_returns_none():
    ex = exit_fill(Direction.LONG, stop_price=95.0, target_price=110.0,
                   bar=Bar(100.0, 105.0, 98.0, 102.0), tick_size=TICK, slip_ticks=SLIP)
    assert ex is None


# --- exit: SHORT stop-loss / take-profit ---------------------------------

def test_short_stop_fills_at_stop_plus_slippage():
    ex = exit_fill(Direction.SHORT, stop_price=105.0, target_price=90.0,
                   bar=Bar(102.0, 106.0, 101.0, 105.0), tick_size=TICK, slip_ticks=SLIP)
    assert ex.reason == "stop"
    assert ex.price == approx(105.0 + SLIP_AMT)


def test_short_stop_gap_up_fills_at_open():
    ex = exit_fill(Direction.SHORT, stop_price=105.0, target_price=90.0,
                   bar=Bar(107.0, 108.0, 106.0, 107.0), tick_size=TICK, slip_ticks=SLIP)
    assert ex.reason == "stop"
    assert ex.price == approx(107.0 + SLIP_AMT)


def test_short_target_fills_at_limit():
    ex = exit_fill(Direction.SHORT, stop_price=105.0, target_price=90.0,
                   bar=Bar(95.0, 96.0, 89.0, 90.0), tick_size=TICK, slip_ticks=SLIP)
    assert ex.reason == "target"
    assert ex.price == approx(90.0)


def test_short_ambiguous_bar_takes_stop_and_flags():
    ex = exit_fill(Direction.SHORT, stop_price=105.0, target_price=90.0,
                   bar=Bar(100.0, 106.0, 89.0, 95.0), tick_size=TICK, slip_ticks=SLIP)
    assert ex.reason == "stop"
    assert ex.ambiguous is True
    assert ex.price == approx(105.0 + SLIP_AMT)
