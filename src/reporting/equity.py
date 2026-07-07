"""Render a clean equity + drawdown image (PNG) from the trades.

One job: a sharp two-panel chart - cumulative net profit (green above zero,
red below) and the underwater drawdown beneath it - saved to disk. NT8-style,
dark, high-DPI. Uses the Agg backend so it never needs a display.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

from src.backtest.engine import Trade  # noqa: E402

_BG = "#1b1b1b"
_GREEN = "#26a269"
_RED = "#c01c28"
_GRID = "#3a3a3a"
_FG = "#d0d0d0"


def plot(trades: list[Trade], path: str | Path, *, title: str = "Equity curve") -> None:
    """Save a cumulative-net-profit + drawdown chart to ``path``."""
    if not trades:
        return
    times = [trades[0].entry_time] + [t.exit_time for t in trades]
    cum = [0.0] + [t.cum_pnl for t in trades]

    peak = cum[0]
    dd = []
    for v in cum:
        peak = max(peak, v)
        dd.append(v - peak)  # <= 0

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(12, 7), height_ratios=[3, 1], sharex=True,
        gridspec_kw={"hspace": 0.08},
    )
    fig.patch.set_facecolor(_BG)

    for ax in (ax1, ax2):
        ax.set_facecolor(_BG)
        ax.grid(True, color=_GRID, linewidth=0.6, alpha=0.7)
        ax.tick_params(colors=_FG, labelsize=8)
        for spine in ax.spines.values():
            spine.set_color(_GRID)

    ax1.axhline(0, color=_FG, linewidth=0.8, alpha=0.6)
    ax1.plot(times, cum, color=_FG, linewidth=1.0)
    ax1.fill_between(times, cum, 0, where=[v >= 0 for v in cum], color=_GREEN, alpha=0.55, interpolate=True)
    ax1.fill_between(times, cum, 0, where=[v < 0 for v in cum], color=_RED, alpha=0.55, interpolate=True)
    ax1.set_ylabel("Cumulative net profit ($)", color=_FG, fontsize=9)
    ax1.set_title(title, color=_FG, fontsize=11, pad=10)

    ax2.fill_between(times, dd, 0, color=_RED, alpha=0.6, interpolate=True)
    ax2.plot(times, dd, color=_RED, linewidth=0.9)
    ax2.set_ylabel("Drawdown ($)", color=_FG, fontsize=9)

    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    fig.autofmt_xdate(rotation=0, ha="center")

    fig.savefig(path, dpi=150, facecolor=_BG, bbox_inches="tight")
    plt.close(fig)
