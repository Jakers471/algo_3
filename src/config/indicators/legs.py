"""Dials for the legs indicator - the staircase between structure points.

A leg is drawn with square corners: a horizontal run at the price of the swing it
left, then a vertical into the swing it arrived at. Diagonal would imply price
travelled in a straight line between the two, which it did not - the candles in
between already say what it did. The right angle claims nothing.

The legs sit *under* the breaks. They are context; a break is an event. So they
are drawn thin and translucent, and the break lines are drawn solid on top.
"""

from __future__ import annotations

ENABLED = True

# --- drawing ----------------------------------------------------------------
DRAW = True

# An up-leg ended above where it began. Muted, because a leg is not news.
UP_COLOR = "rgba(38, 166, 154, 0.55)"
DOWN_COLOR = "rgba(239, 83, 80, 0.55)"

WIDTH = 1
