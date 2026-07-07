"""Export the walk-forward per-fold table - machine (CSV) + human (text).

One job: one row per fold - its IS/OOS windows, the params picked in-sample,
and the IS vs OOS score - so you can see param stability and whether the
in-sample edge held out of sample.
"""

from __future__ import annotations

import csv
from pathlib import Path

_TS = "%Y-%m-%d"

COLUMNS = [
    "fold", "is_start", "is_end", "oos_start", "oos_end",
    "best_params", "is_score", "oos_score", "n_oos_trades",
]


def _row(fr) -> dict:
    f = fr.fold
    return {
        "fold": f.num,
        "is_start": f.is_start.strftime(_TS),
        "is_end": f.is_end.strftime(_TS),
        "oos_start": f.oos_start.strftime(_TS),
        "oos_end": f.oos_end.strftime(_TS),
        "best_params": ";".join(f"{k}={v}" for k, v in fr.best_params.items()),
        "is_score": f"{fr.is_score:.4f}",
        "oos_score": f"{fr.oos_score:.4f}",
        "n_oos_trades": fr.n_oos_trades,
    }


def write_csv(fold_results, path: str | Path) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(_row(fr) for fr in fold_results)


def write_text(fold_results, path: str | Path) -> None:
    rows = [_row(fr) for fr in fold_results]
    widths = {c: len(c) for c in COLUMNS}
    for r in rows:
        for c in COLUMNS:
            widths[c] = max(widths[c], len(str(r[c])))
    header = "  ".join(c.ljust(widths[c]) for c in COLUMNS)
    lines = [header, "-" * len(header)]
    for r in rows:
        lines.append("  ".join(str(r[c]).ljust(widths[c]) for c in COLUMNS))
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")
