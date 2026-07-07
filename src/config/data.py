"""Market-data configuration: default instrument, lookback, and bar limits."""

# E-mini Nasdaq-100 future (not the Micro, which is F.US.MNQ).
DEFAULT_SYMBOL_SEARCH = "NQ"
DEFAULT_SYMBOL_ID = "F.US.ENQ"

# History request defaults.
DEFAULT_LOOKBACK_DAYS = 7
DEFAULT_BAR_LIMIT = 200
