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
