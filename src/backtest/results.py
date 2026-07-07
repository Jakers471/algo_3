"""Turn a list of Trades into performance metrics and a printed report.

One job: aggregate closed trades into the numbers you judge a strategy by,
including how much of the result rests on the adverse-first assumption
(ambiguous same-bar resolutions) - so an optimistic fill model can't hide.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.backtest.engine import Trade
from src.core import console


@dataclass
class Metrics:
    n_trades: int
    wins: int
    losses: int
    win_rate: float
    total_pnl: float
    final_equity: float
    return_pct: float
    profit_factor: float
    avg_win: float
    avg_loss: float
    expectancy: float
    max_drawdown: float
    max_drawdown_pct: float
    n_stop: int
    n_target: int
    n_session: int
    n_ambiguous: int
    ambiguous_pct: float
    n_same_bar: int


def summarize(trades: list[Trade], starting_capital: float) -> Metrics:
    n = len(trades)
    wins = [t for t in trades if t.pnl_dollars > 0]
    losses = [t for t in trades if t.pnl_dollars <= 0]
    gross_profit = sum(t.pnl_dollars for t in wins)
    gross_loss = -sum(t.pnl_dollars for t in losses)  # positive magnitude
    total = sum(t.pnl_dollars for t in trades)

    equity = starting_capital
    peak = starting_capital
    max_dd = 0.0
    for t in trades:
        equity += t.pnl_dollars
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)

    n_amb = sum(t.ambiguous for t in trades)
    return Metrics(
        n_trades=n,
        wins=len(wins),
        losses=len(losses),
        win_rate=len(wins) / n if n else 0.0,
        total_pnl=total,
        final_equity=starting_capital + total,
        return_pct=total / starting_capital * 100 if starting_capital else 0.0,
        profit_factor=(gross_profit / gross_loss) if gross_loss else float("inf"),
        avg_win=gross_profit / len(wins) if wins else 0.0,
        avg_loss=-gross_loss / len(losses) if losses else 0.0,
        expectancy=total / n if n else 0.0,
        max_drawdown=max_dd,
        max_drawdown_pct=max_dd / peak * 100 if peak else 0.0,
        n_stop=sum(t.reason == "stop" for t in trades),
        n_target=sum(t.reason == "target" for t in trades),
        n_session=sum(t.reason == "session" for t in trades),
        n_ambiguous=n_amb,
        ambiguous_pct=n_amb / n * 100 if n else 0.0,
        n_same_bar=sum(t.same_bar for t in trades),
    )


def _money(x: float) -> str:
    color = console.GREEN if x >= 0 else console.RED
    return console.paint(f"${x:,.2f}", color)


def report(m: Metrics, *, title: str = "Backtest results") -> None:
    """Print a compact, color-coded performance summary."""
    print()
    print(console.paint(f"  {title}", console.BOLD, console.CYAN))
    print(f"  {'trades':<16}{m.n_trades:,}")
    print(f"  {'win rate':<16}{m.win_rate * 100:.1f}%   ({m.wins}W / {m.losses}L)")
    print(f"  {'net pnl':<16}{_money(m.total_pnl)}   ({m.return_pct:+.1f}%)")
    print(f"  {'final equity':<16}{_money(m.final_equity)}")
    print(f"  {'profit factor':<16}{m.profit_factor:.2f}")
    print(f"  {'expectancy':<16}{_money(m.expectancy)} / trade")
    print(f"  {'avg win/loss':<16}{_money(m.avg_win)} / {_money(m.avg_loss)}")
    print(f"  {'max drawdown':<16}{_money(-m.max_drawdown)}   ({m.max_drawdown_pct:.1f}%)")
    print(f"  {'exits':<16}{m.n_target} target, {m.n_stop} stop, {m.n_session} session")
    amb = console.paint(
        f"{m.n_ambiguous} ({m.ambiguous_pct:.1f}%)",
        console.YELLOW if m.n_ambiguous else console.DIM,
    )
    print(f"  {'ambiguous':<16}{amb}   " + console.paint("adverse-first, same-bar stop+target", console.DIM))
    print(f"  {'same-bar exits':<16}{m.n_same_bar}")
    print()
