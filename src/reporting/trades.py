"""Export the trade list - machine (CSV) and human (aligned text).

One job: write every closed Trade with the columns NT8's trade list shows
that we actually have (no Clearing/Exchange/IP/NFA fees - we only have
commission), plus our ambiguous / same-bar honesty flags.
"""

from __future__ import annotations

import csv
from pathlib import Path

from src.backtest.engine import Trade

_TS = "%Y-%m-%d %H:%M"

COLUMNS = [
    "num", "direction", "qty", "entry_time", "exit_time", "entry_price", "exit_price",
    "exit_reason", "profit", "cum_profit", "commission", "bars", "mae", "mfe", "etd",
    "ambiguous", "same_bar",
]


def _row(t: Trade) -> dict:
    return {
        "num": t.num,
        "direction": t.direction.value,
        "qty": t.size,
        "entry_time": t.entry_time.strftime(_TS),
        "exit_time": t.exit_time.strftime(_TS),
        "entry_price": f"{t.entry_price:.2f}",
        "exit_price": f"{t.exit_price:.2f}",
        "exit_reason": t.reason,
        "profit": f"{t.pnl_dollars:.2f}",
        "cum_profit": f"{t.cum_pnl:.2f}",
        "commission": f"{t.commission:.2f}",
        "bars": t.bars,
        "mae": f"{t.mae:.2f}",
        "mfe": f"{t.mfe:.2f}",
        "etd": f"{t.etd:.2f}",
        "ambiguous": int(t.ambiguous),
        "same_bar": int(t.same_bar),
    }


def write_csv(trades: list[Trade], path: str | Path) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(_row(t) for t in trades)


def write_text(trades: list[Trade], path: str | Path) -> None:
    widths = {c: len(c) for c in COLUMNS}
    rows = [_row(t) for t in trades]
    for r in rows:
        for c in COLUMNS:
            widths[c] = max(widths[c], len(str(r[c])))
    header = "  ".join(c.rjust(widths[c]) for c in COLUMNS)
    lines = [header, "-" * len(header)]
    for r in rows:
        lines.append("  ".join(str(r[c]).rjust(widths[c]) for c in COLUMNS))
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")
