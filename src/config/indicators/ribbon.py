"""Dials for the ribbon indicator - a fan of moving averages, coloured by slope.

The ribbon is COUNT simple moving averages of the close, their periods spread
evenly from START in steps of STEP. Drawn together they fan out: the short ones
hug price, the long ones lag it, and the spread between them is the market's
recent trend made visible.

Each line is coloured by its OWN slope, bar to bar - green where it turned up
from the last bar, red where it turned down. So a healthy trend is a fan of one
colour and a turn is the fan changing colour from the short end inward.

The periods are simple averages, not exponential: an SMA is exactly the mean of
the last `period` closes and refuses to publish until it has that many, which is
the same honesty every other indicator here keeps - a partial average is a
different number, not a rougher one.
"""

from __future__ import annotations

ENABLED = True

# --- the fan ----------------------------------------------------------------
# COUNT moving averages, periods START, START+STEP, ... A wider STEP fans the
# lines further apart; a larger COUNT reaches further back. The longest period
# is START + (COUNT - 1) * STEP bars, which is also how many bars the ribbon
# needs before every line is drawn.
COUNT = 32
START = 5
STEP = 5

# The periods themselves, derived once so the indicator and any reader agree.
PERIODS = tuple(START + i * STEP for i in range(COUNT))

# --- drawing ----------------------------------------------------------------
# Off by default: 32 lines x one segment per bar is 157K marks over a
# 5,000-bar warmup - measured at 1.25s of JSON alone, dominating a replay
# seed's payload (41 MB total). The Layers checkbox does NOT gate this - it
# is visibility only (config/chart.py), so hiding the layer in the browser
# still pays this cost. This is the dial that actually stops it. `regime`
# still reads the fan's numbers regardless (ENABLED stays True); only the
# drawing is off.
DRAW = False

# A line coloured by the sign of its slope since the previous bar. Green up, red
# down - the same green and red as the candles and the delta strip, so the whole
# chart speaks one colour language. Translucent, because thirty-two lines drawn
# solid would be a wall; layered, they read as a fan with depth.
UP_COLOR = "rgba(38, 166, 154, 0.55)"
DOWN_COLOR = "rgba(239, 83, 80, 0.55)"

WIDTH = 1
