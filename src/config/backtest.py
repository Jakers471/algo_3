"""Backtest configuration.

One job: hold the dials the backtest engine runs on. Split into two groups:
data-truth settings that the audit *dictates* (non-negotiable — the engine
must honor them or the results are wrong), and backtest *choices* informed by
the audit that you are free to tune.
"""

from __future__ import annotations

from datetime import date

from src.audit import reader as audit

# --- data-truth settings (dictated by DATA_AUDIT.json) --------------------
# The last bar in the dataset — ~17 months behind live (audit: stale_data).
DATA_END = audit.DATA_END
# Bars carry no bid/ask, so fills can't be derived; model >=1 tick of
# slippage (audit: fills_no_quotes, required).
SLIPPAGE_TICKS = 1
# Deep history is back-adjusted (synthetic absolute levels); express stops and
# targets in point distance, never % or absolute price (audit: back_adjustment).
USE_POINT_DISTANCE = True
# Negligible (<0.01%) zero-volume overnight bars; tolerate, don't skip
# (audit: zero_volume_bars, info). Never divide by volume blindly.
SKIP_ZERO_VOLUME_BARS = False

# --- backtest choices (informed by the audit; tune freely) ----------------
# Backtest recent years — pre-2015 levels are increasingly synthetic from
# back-adjustment (audit: back_adjustment). Move earlier only knowingly.
BACKTEST_START = date(2015, 1, 1)
# Account size to simulate.
STARTING_CAPITAL = 50_000.0
# PLACEHOLDER — set to your TopstepX commission per contract per side.
COMMISSION_PER_SIDE = 0.0
# Explicit hold policy across session gaps (audit: gap_awareness, required):
# never carry a position across the overnight/weekend boundary by default.
ALLOW_OVERNIGHT_HOLD = False
ALLOW_WEEKEND_HOLD = False
