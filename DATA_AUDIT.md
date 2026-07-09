# DATA_AUDIT.md — backtest data reference

_Machine-readable twin: `DATA_AUDIT.json`. Regenerate both by re-running the audit._

**Verdict: CLEAN** — all NQ/ES Parquet files passed every integrity check. The only large gaps are Christmas/New-Year exchange closures, not data holes.

## Coverage & integrity

| File | Rows | Range | Dupes | NaNs | OHLC bad | Non-pos | Neg vol | Zero-vol % |
|------|------|-------|-------|------|----------|---------|---------|-----------|
| `NQ_15m.parquet` | 464,919 | 2005-01-11 → 2025-01-10 | 0 | 0 | 0 | 0 | 0 | 0.0022% |
| `NQ_1d.parquet` | 5,046 | 2005-01-11 → 2025-01-10 | 0 | 0 | 0 | 0 | 0 | 0.0198% |
| `NQ_1m.parquet` | 6,225,528 | 2005-01-11 → 2025-01-10 | 0 | 0 | 0 | 0 | 0 | 0.0021% |
| `NQ_5m.parquet` | 1,364,414 | 2005-01-11 → 2025-01-10 | 0 | 0 | 0 | 0 | 0 | 0.0027% |
| `NQ_60m.parquet` | 117,869 | 2005-01-12 → 2025-01-10 | 0 | 0 | 0 | 0 | 0 | 0.0% |
| `ES_15m.parquet` | 475,116 | 2005-01-11 → 2025-01-10 | 0 | 0 | 0 | 0 | 0 | 0.0021% |
| `ES_1m.parquet` | 6,736,660 | 2005-01-11 → 2025-01-10 | 0 | 0 | 0 | 0 | 0 | 0.0038% |
| `ES_5m.parquet` | 1,402,331 | 2005-01-11 → 2025-01-10 | 0 | 0 | 0 | 0 | 0 | 0.0035% |
| `ES_60m.parquet` | 122,545 | 2005-01-11 → 2025-01-10 | 0 | 0 | 0 | 0 | 0 | 0.0% |

## Gaps & sessions

Base spacing = the timeframe interval. Above that, gaps are: a daily ~1h maintenance halt (intraday), ~49h weekends, and holiday closures. **The same 7 >75h gaps appear in every intraday file — all Christmas/New-Year closures:**

- `2006-12-22` → `2006-12-26`  (85.8h)
- `2006-12-29` → `2007-01-02`  (85.8h)
- `2011-12-23` → `2011-12-27`  (85.8h)
- `2011-12-30` → `2012-01-03`  (85.8h)
- `2009-12-24` → `2009-12-27`  (76.8h)
- `2015-12-24` → `2015-12-27`  (76.8h)
- `2020-12-24` → `2020-12-27`  (76.8h)

~34 missing weekdays over 20 years = exchange holidays. **No unexpected data holes.**

## Contract specs (for sizing & fills)

| Symbol | Instrument | Tick | $/tick | $/point |
|--------|-----------|------|--------|---------|
| NQ | E-mini Nasdaq-100 | 0.25 | $5.0 | $20.0 |
| ES | E-mini S&P 500 | 0.25 | $12.5 | $50.0 |

## What the backtest pipeline MUST handle

- **REQUIRED** — **gap_awareness**: Bars have session gaps: a daily ~1h maintenance halt, ~49h weekends, and holiday closures. The engine must treat these as session boundaries - never as a tradeable move. Don't compute returns across a gap as if continuous; decide an overnight/weekend hold policy explicitly.
- **REQUIRED** — **back_adjustment**: Continuous series is back-adjusted: absolute price levels in deep history are synthetic (offset grows going back, ~+3000pt near 2005). Use point-distance logic (stops/targets in points), not absolute-price levels or % returns, on old data. Backtest recent years for live-realistic levels.
- WARNING — **stale_data**: Data ends 2025-01-10 - ~17 months behind live. The current market regime is absent until the gap is filled (e.g. via API/tick contracts).
- **REQUIRED** — **fills_no_quotes**: Bars contain NO bid/ask. Fill prices cannot be derived from them - model slippage (>=1 tick). Calibrate against the desktop tick dataset (has bid/ask).
- info — **zero_volume_bars**: A negligible number of zero-volume bars exist (<0.01%) in thin overnight minutes. Tolerate or skip; do not divide by volume blindly.
- **REQUIRED** — **timezone**: All timestamps are tz-aware UTC. Keep everything UTC internally; convert to US/Eastern only for session logic. Session windows are EASTERN (18:00->03:00 Asia, 03:00->08:00 London, 08:00->17:00 NY); the 17:00-18:00 ET gap is the CME maintenance halt. Using America/Chicago with those numbers silently drops the 17:00-18:00 ET trading hour into no session.
- **REQUIRED** — **bar_stamping**: Bars are CLOSE-stamped: a bar labelled T covers (T-step, T]. Verified - 1m bars aggregate into 5m exactly (OHLC and volume) with closed='right', label='right'. Consequences: a bar stamped T is fully known at T, so revealing it at T leaks nothing; and any interval membership test (sessions, windows) must be start < t <= end, or the closing bar of each session belongs to nothing.
- info — **tick_dataset**: A separate NT8 tick dataset exists outside the repo (Desktop/NQ_Tick_Data): 10 NQ contracts, 2024-03-12 -> 2026-07-03, ~300M ticks with bid/ask. It is UTC, 52% of ticks share a timestamp with a neighbour (time is NOT a unique key), and tick-rebuilt bars reconcile with these Parquet bars to 0.0012% on total volume. Order flow (delta, absorption, sweeps, spread) is computable ONLY from it - never from these bars.
