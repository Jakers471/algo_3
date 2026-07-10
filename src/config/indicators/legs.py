"""Dials for the legs indicator - the staircase between structure points.

A leg is drawn as one straight line between the two swings it joins. It is not a
claim that price travelled that path: the candles under it already say what price
did, and the line names only the two ends and the slope between them.

The legs sit *under* the breaks. They are context; a break is an event. So a leg
is thin, muted and solid, and a break is thin, bright and dashed - the dash is
what tells them apart, because both are red and green and hue alone would not.
"""

from __future__ import annotations

ENABLED = True

# --- drawing ----------------------------------------------------------------
DRAW = True

# An up-leg ended above where it began. Muted, because a leg is not news: it is
# the context a break is news against.
UP_COLOR = "rgba(38, 166, 154, 0.55)"
DOWN_COLOR = "rgba(239, 83, 80, 0.55)"

WIDTH = 1
