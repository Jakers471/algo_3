"""Serve OHLCV bars to the browser chart, fast.

``packer`` builds a flat binary cache from the Parquet store; ``store`` slices
it off a memmap; ``api`` gives those slices meaning; ``server`` speaks HTTP.
The frontend that consumes them lives at top-level ``frontend/chart/``.
"""
