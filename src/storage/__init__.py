"""Storage package: persist market data to disk.

One category: turning in-memory data (API bars, results) into files under
the top-level data/ dir, and reading them back. Format details live here so
callers don't repeat them.
"""
