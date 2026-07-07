# Data — NinjaTrader 8 (NT8) export

OHLCV futures bar data exported from **NinjaTrader 8**.

## Contents

| Symbol | Timeframes | Rows (1m) | Date range (UTC) |
|--------|------------|-----------|------------------|
| NQ (E-mini Nasdaq-100) | 1m, 5m, 15m, 60m, 1d | 6,225,528 | 2005-01-11 → 2025-01-10 |
| ES (E-mini S&P 500)    | 1m, 5m, 15m, 60m      | 6,736,660 | 2005-01-11 → 2025-01-10 |

> Note: ES has no `1d` file; NQ does.

## Format

- One Parquet file per symbol/timeframe: `<SYMBOL>_<TF>.parquet` (e.g. `NQ_1m.parquet`).
- Columns: `open`, `high`, `low`, `close`, `volume`.
- Datetime index in **UTC**.

## Source

Exported from NinjaTrader 8 (NT8). Continuous contract data.

_Not tracked in git (see `.gitignore` — `data/` is ignored due to size, ~242 MB)._
