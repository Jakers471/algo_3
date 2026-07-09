# Data — NinjaTrader 8 (NT8) export

OHLCV futures bar data exported from **NinjaTrader 8**.

## Contents

| Symbol | Timeframes | Rows (1m) | Date range (UTC) |
|--------|------------|-----------|------------------|
| NQ (E-mini Nasdaq-100) | 1m, 5m, 15m, 60m, 1d | 6,225,528 | 2005-01-11 → 2025-01-10 |
| ES (E-mini S&P 500)    | 1m, 5m, 15m, 60m      | 6,736,660 | 2005-01-11 → 2025-01-10 |

> Note: ES has no `1d` file; NQ does.

## Format

- One Parquet file per symbol/timeframe, under a per-symbol folder: `<SYMBOL>/<SYMBOL>_<TF>.parquet` (e.g. `NQ/NQ_1m.parquet`).
- Columns: `open`, `high`, `low`, `close`, `volume`. Volume **is** present and accurate.
- Datetime index in **UTC**.
- Bars are **close-stamped**: a bar labelled `T` covers `(T - step, T]`. Verified — 1m bars aggregate into 5m exactly, OHLC *and* volume. So a bar stamped `T` is fully known at `T`, and any interval test must be `start < t <= end`.
- Continuous, **back-adjusted** series (see `DATA_AUDIT.md`).
- **No bid/ask.** These bars cannot carry order flow — signed volume (delta), absorption, sweeps and spread are not recoverable from them. That needs the tick dataset below.

## Quality audit

Integrity, gaps, and how the backtest pipeline must handle this data: `DATA_AUDIT.md` (human) / `DATA_AUDIT.json` (machine), at the repo root.

## `NQT/` — bars rebuilt from ticks (a separate dataset)

| Timeframe | Bars | Range (UTC) |
|---|---|---|
| 15s, 1m, 5m, 15m, 60m, 4h | 3.2M … 3.8k | 2024-03-12 → 2026-07-03 |

Built by `python -m src.cli.resample` from the tick file below. Columns: the usual
`open/high/low/close/volume`, **plus `delta`, `buy_volume`, `sell_volume`, `trades`** —
signed order flow, computed exactly from each tick's aggressor side (a trade printing at
the ask is a buy, at the bid a sell). Only 1,527 contracts of 321,879,452 — 0.000474% —
print strictly between the bid and ask; those join neither side rather than being guessed
into one, so `buy_volume + sell_volume` can fall a contract short of `volume` on 0.09% of bars.

- Prices are **back-adjusted**, re-anchored so the newest contract keeps its real prices
  (offset `+2187.00`). Raw prices jump 211–270 points at each quarterly roll.
- **Do not mix `NQT` with `NQ`.** Different back-adjustment anchors; absolute prices are
  not comparable.
- `15s` exists only here. Bars cannot be subdivided, only ticks can.

## Tick data (separate, outside the repo)

`Desktop/NQ_Tick_Data/` holds the NT8 tick export: 10 NQ contracts, **2024-03-12 → 2026-07-03**, ~300M ticks with `price`, `bid`, `ask`, `volume`. It is UTC like these bars, and it reconciles with them to **0.0012%** on total volume over the overlapping window. It is the only source of order flow, and the only source fine enough to build a 15s timeframe.

Note it does **not** overlap these bars after 2025-01-10: bars end there, tick history begins 2024-03. See `BUILD_PLAN.md`.

## Source

Exported from NinjaTrader 8 (NT8). Continuous contract data.

_Not tracked in git (see `.gitignore` — `data/` is ignored due to size, ~242 MB)._
