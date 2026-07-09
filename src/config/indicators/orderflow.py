"""Dials for the order-flow indicator.

One job: hold what order flow publishes and how the chart paints it. The values
themselves come from the bars - they were computed once, exactly, from each
tick's aggressor side (see src/data/resample.py) - so there is nothing to tune
here, only what to show.
"""

from __future__ import annotations

ENABLED = True

# Draw delta as a signed histogram in its own strip beneath the price.
DRAW_DELTA = True

# Aggressive buying above the zero line, aggressive selling below.
DELTA_UP = "rgba(38, 166, 154, 0.85)"
DELTA_DOWN = "rgba(239, 83, 80, 0.85)"

# Where that strip sits, as fractions of the pane height (0 = top, 1 = bottom).
# It lives above the volume strip and below the candles.
PANE_TOP = 0.72
PANE_BOTTOM = 0.17
