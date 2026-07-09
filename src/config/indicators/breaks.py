"""Dials for the breaks indicator - where a swing level was taken out.

The drawing runs from the swing bar that set the level, forward along the level,
to the bar that closed through it, and then drops (or lifts) to that bar's close.
So the horizontal says "this level stood from here to here" and the vertical says
"and this is what went through it".

Green means a swing high was taken out; red means a swing low was. These are the
same green and red as the candles, deliberately: a break up is the same kind of
news as an up bar, only larger.
"""

from __future__ import annotations

ENABLED = True

# A break is a CLOSE beyond the level, not a wick through it. A high that pierces
# a swing high and closes back below it is a rejection of that level, not a break
# of it. Set False to test the wick definition instead.
USE_CLOSE = True

# --- drawing ----------------------------------------------------------------
DRAW = True

UP_COLOR = "#26a69a"     # a swing high was taken out
DOWN_COLOR = "#ef5350"   # a swing low was taken out

WIDTH = 2
