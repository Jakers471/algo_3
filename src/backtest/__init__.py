"""Backtest area: resolve bracket orders against bars into fills, PnL, stats.

The offline twin of live execution. ``engine.run()`` walks the bars, arms the
strategy's stop entries, resolves fills (fills.py), and produces Trades;
results.py turns those into metrics. Fill assumptions are conservative and
swappable behind fills.py.
"""
