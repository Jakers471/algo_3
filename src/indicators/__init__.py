"""Indicators: shared raw math, pure and reusable. Strategies compose these.

Plumbing, not opinions - an OHLCV window in, numbers out, no trade decisions.
volume_profile.py is the POC/value-area core; grade.py reduces a window to a
regime. A strategy imports what it needs and turns the output into signals.
"""
