"""Print the All / Long / Short summary to the terminal, color-coded.

One job: the at-a-glance version of stats.py for the CLI. Reuses stats' row
spec and formatter so the terminal and the saved summary.txt never drift.
"""

from __future__ import annotations

from src.core import console
from src.reporting import stats as stats_mod

_SCOPES = ("all", "long", "short")
_LABEL_W = 26
_COL_W = 15


def _cell(kind: str, s, key: str) -> str:
    text = stats_mod._fmt(kind, s, key).rjust(_COL_W)
    v = getattr(s, key)
    if key == "net_profit":
        return console.paint(text, console.GREEN if v >= 0 else console.RED)
    if key in ("ambiguous", "ambiguous_pct") and v:
        return console.paint(text, console.YELLOW)
    return text


def report(stats: dict, *, title: str = "Backtest results") -> None:
    print()
    print(console.paint(f"  {title}", console.BOLD, console.CYAN))
    header = f"  {'Performance':<{_LABEL_W}}" + "".join(sc.capitalize().rjust(_COL_W) for sc in _SCOPES)
    print(console.paint(header, console.BOLD))
    print(console.paint("  " + "-" * (len(header) - 2), console.DIM))
    for label, key, kind in stats_mod._ROWS:
        row = f"  {label:<{_LABEL_W}}" + "".join(_cell(kind, stats[sc], key) for sc in _SCOPES)
        print(row)
    print()


def report_folds(fold_results, objective: str, wfe: float) -> None:
    """Print the walk-forward per-fold table and the efficiency line."""
    print()
    print(console.paint(f"  Walk-forward folds  (objective: {objective})", console.BOLD, console.CYAN))
    header = f"  {'#':>3}  {'OOS window':<23}  {'best params':<40}  {'IS':>9}  {'OOS':>9}  {'trades':>6}"
    print(console.paint(header, console.BOLD))
    print(console.paint("  " + "-" * (len(header) - 2), console.DIM))
    for fr in fold_results:
        window = f"{fr.fold.oos_start.date()}..{fr.fold.oos_end.date()}"
        params = ", ".join(f"{k}={v}" for k, v in fr.best_params.items())
        oos_color = console.GREEN if fr.oos_score > 0 else console.RED
        oos = console.paint(f"{fr.oos_score:>9.3f}", oos_color)
        print(f"  {fr.fold.num:>3}  {window:<23}  {params:<40}  {fr.is_score:>9.3f}  {oos}  {fr.n_oos_trades:>6}")
    color = console.GREEN if wfe >= 0.5 else console.YELLOW if wfe > 0 else console.RED
    print()
    print("  " + console.paint(f"Walk-forward efficiency: {wfe:.2f}", console.BOLD, color)
          + console.paint("   (mean OOS score / mean IS score; ~1.0 = robust)", console.DIM))
    print()
