"""Strategy area: turn bars into bracket order intents (entry stop + SL/TP).

A strategy holds its own parameters (the dials that define it) and, given
bars, emits the resting stop-entry levels the backtest/execution engines
resolve into fills. It knows nothing about money or fills - only signals.
"""
