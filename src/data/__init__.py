"""Data area: load the NT8 Parquet store into clean, session-aware bars.

``from src.data import prepare`` then ``prepare.get_bars('NQ', '5m')`` is the
public entry: it reads the raw Parquet (loader.py) and applies the audit's
data-truth rules - window, gap marking, zero-volume policy (prepare.py).
Every downstream engine (strategy, backtest) consumes these bars.
"""
