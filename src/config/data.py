"""Market-data configuration: default instrument, lookback, and bar limits."""

# E-mini Nasdaq-100 future (not the Micro, which is F.US.MNQ).
DEFAULT_SYMBOL_SEARCH = "NQ"
DEFAULT_SYMBOL_ID = "F.US.ENQ"

# History request defaults.
DEFAULT_LOOKBACK_DAYS = 7
DEFAULT_BAR_LIMIT = 200

# Bulk fetch: which timeframes to pull & save (names from history.TIMEFRAMES).
FETCH_TIMEFRAMES = ["1m", "5m", "15m", "60m", "1d"]

# Where saved market data lands (top-level, git-ignored).
DATA_DIR = "data"
