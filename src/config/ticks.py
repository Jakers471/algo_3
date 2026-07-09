"""Settings for the tick dataset and the bars rebuilt from it.

One job: hold where the ticks live, what we rebuild from them, and under what
name. The tick data is a SEPARATE dataset from the NT8 bar files - different
span, different back-adjustment anchor - and it is named separately so nothing
ever silently mixes the two.
"""

from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]

# The stitched continuous tick file (outside the repo; ~2 GB, 296M rows).
TICK_FILE = Path.home() / "Desktop" / "NQ_Tick_Data" / "NQ_continuous_ticks.parquet"

# Bars rebuilt from ticks land under this symbol, never under "NQ". The NT8 bar
# files and these do not share a back-adjustment anchor, so their absolute prices
# are not comparable. Keeping the names apart makes an accidental mix impossible.
OUTPUT_SYMBOL = "NQT"

# Everything is resampled from this base. 15s divides every timeframe below, so
# the ticks are streamed exactly once and the rest are folded up from the result.
# (Deriving 1m from 15s is exact; re-reading 296M ticks per timeframe is not.)
BASE_TIMEFRAME = "15s"
DERIVED_TIMEFRAMES = ("30s", "1m", "5m", "15m", "60m", "4h")

# Pandas offset per timeframe. Bars are CLOSE-stamped, like the NT8 store:
# a bar labelled T covers (T - step, T].
FREQ = {
    "15s": "15s",
    "30s": "30s",
    "1m": "1min",
    "5m": "5min",
    "15m": "15min",
    "60m": "60min",
    "4h": "4h",
}

# Parquet row groups read per chunk. One group is ~1M ticks and ~0.1 s.
ROW_GROUPS_PER_CHUNK = 8

# Columns every rebuilt bar carries. The last four are the reason ticks exist:
# they are exact, not proxies, and no bar file can ever supply them.
COLUMNS = ("open", "high", "low", "close", "volume",
           "delta", "buy_volume", "sell_volume", "trades")
