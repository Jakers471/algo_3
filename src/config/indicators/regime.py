"""Dials for the regime indicator - reading the ribbon's shape as a regime.

The 32-line ribbon collapses to three dimensionless numbers, and those three
place the market in a regime:

- ALIGNMENT  - are the lines stacked in period order? +1 is a clean up-trend
  (short over long), -1 a clean down-trend, 0 a scrambled, directionless fan.
- AGREEMENT  - are the lines all sloping the same way this bar? +1 all rising,
  -1 all falling. Faster than alignment; it turns first.
- WIDTH      - how flared is the fan, measured in range_scale so it survives a
  change of volatility regime. Wide is conviction; a pinch is a coiled spring.

Every threshold here is dimensionless (alignment) or in multiples of range_scale
(width), never in points - the same discipline as `swing`'s RETRACE, so a cutoff
set in a quiet month still means the same thing in a loud one. The numbers below
were measured, not guessed: see `scratch/analysis/ribbon_regime.py`, which prints
the alignment/width/agreement distributions over real NQT bars.
"""

from __future__ import annotations

ENABLED = True

# --- the cutoffs (measured; see scratch/analysis/ribbon_regime.py) -----------
# A trend needs the lines stacked in order (|alignment| at or above this) AND the
# fan flared past WIDTH_TREND range_scales. Below WIDTH_PINCH the fan is a squeeze
# - a regime loading, not a regime - whatever the alignment says.
# Measured on 163,255 warm NQT 5m bars: width has p10 2.0, p50 4.9, p75 8.1; and
# |alignment| p50 0.48, p75 0.74. So a squeeze is the low tail of width (~p10), a
# trend is a flare past the median AND lines stacked past ~p60 of alignment.
ALIGN_TREND = 0.60
WIDTH_TREND = 5.0
WIDTH_PINCH = 2.0

# A new regime must hold this many consecutive bars before it is adopted, so the
# label does not chatter every time price grazes a boundary. 1 disables it.
CONFIRM_BARS = 3

# --- drawing ----------------------------------------------------------------
# A dashed vertical rule when the regime CHANGES, labelled with the new regime.
# The whole thing is one Layers toggle ("Regime"); the readings ride the table
# whether it is drawn or not.
DRAW = True

# Colour per regime: green up-trend, red down, amber the coiled squeeze, grey the
# directionless chop - the same language the rest of the chart already speaks.
LINE_COLORS = {
    "up":         "rgba(63, 185, 80, 0.70)",
    "down":       "rgba(239, 83, 80, 0.70)",
    "transition": "rgba(210, 153, 34, 0.70)",
    "chop":       "rgba(125, 133, 144, 0.55)",
}
LABEL_COLORS = {
    "up":         "rgba(86, 211, 100, 0.95)",
    "down":       "rgba(244, 129, 127, 0.95)",
    "transition": "rgba(227, 179, 65, 0.95)",
    "chop":       "rgba(160, 169, 180, 0.90)",
}
# CSS pixels from the top the regime label sits at. Below the session labels
# (~6) and their close labels (~22), so three kinds of rule never collide.
LABEL_Y = 38
