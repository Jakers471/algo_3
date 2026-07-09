"""Dials for the swing indicator - where the structure points land.

``RETRACE`` is the only real dial, and it is expressed in multiples of
``range_scale``, never in points. A swing is confirmed when price pulls back
that far from the running extreme.

**It chooses density, not which timeframe dominates.** Raising it thins every
rung at once. Swings per NY session, measured over 658 sessions of NQ with these
very indicators:

    RETRACE      30s      3m     15m    | rung spacing
       1.0     277.0    47.3    9.24    |  /5.9  /5.1
       1.5     160.9    26.8    5.50    |  /6.0  /4.9
       2.0     101.6    16.8    3.64    |  /6.0  /4.6
       3.0      49.2     8.4    1.99    |  /5.9  /4.2
       4.0      29.3     5.4    1.31    |  /5.4  /4.1
       6.0      14.2     2.9    0.71    |  /4.8  /4.1
      10.0       5.8     1.5    0.33    |  /3.9  /4.5

Read the right-hand column: whatever you choose, each rung stays 5-7x sparser
than the one below it. That spacing is a property of the 30s/3m/15m ladder being
evenly spaced in bar range (range grows as t^0.507, so equal time ratios give
equal range ratios) and no setting of RETRACE can rescue an uneven ladder - nor
break an even one.

What the dial does choose is what "structure" means. Near 1.5, the 15m rung
sketches the shape of a session (~6 swings). Near 3, it marks little more than
the day's high and low (~2). Past 6 it stops producing structure at all - a
swing every few days - and the 30s rung inherits the job the 15m rung was
doing. That is a legitimate choice; it is not the same system.
"""

from __future__ import annotations

ENABLED = True

# A swing is confirmed after price retraces this many multiples of the current
# range_scale from the running extreme. Points would be wrong: NQ's median 30s
# range moved 4.50 -> 14.25 across 29 months, a 3.17x swing.
RETRACE = 6.0

# --- drawing ----------------------------------------------------------------
# Off: the legs and breaks drawn from these points carry the structure now, and
# an arrow on every swing as well was two drawings of one fact. The field is
# still published, so the table shows it and `legs` and `breaks` read it.
#
# Turn it back on to see exactly which bar each leg springs from - the arrow
# lands on the bar that MADE the extreme, not the later one that confirmed it.
DRAW_MARKERS = False

# Structure is not directional information: a swing high and a swing low are the
# same kind of thing. Position and shape already say which. One colour.
MARKER_COLOR = "#58a6ff"

HIGH_SHAPE = "arrowDown"   # drawn above the bar
LOW_SHAPE = "arrowUp"      # drawn below it

# --- the provisional rails ---------------------------------------------------
# The standing high, the standing low, and the price at which the provisional one
# confirms. Drawn as full-width price lines with a label on the axis, NOT as
# segments.
#
# They were segments once, running from the bar that made the extreme to the
# current bar, and it was wrong. Measured on 54,564 15m bars: while price runs it
# makes a new high on the current bar, so that segment had ZERO length 25% of the
# time and two bars or fewer 43% of the time - invisible, in exactly the case the
# rails were added for. A level standing right now has no start. Only `legs` and
# `breaks`, which are historical facts, have a beginning and an end.
DRAW_RAILS = True

# The rail in the hunting direction is still moving - a claim about where price
# has been, not yet about where it turned. Pale, so it reads as unfinished.
LIVE_RAIL_COLOR = "rgba(201, 209, 217, 0.75)"

# The other rail froze at the last confirmed swing. Dimmer: it is history, and
# `breaks` will light it green or red if price ever closes through it.
FROZEN_RAIL_COLOR = "rgba(125, 133, 144, 0.45)"

# Where the provisional extreme becomes a swing. Dashed, because nothing has
# happened there yet - it is a condition, not a level the market has respected.
TRIGGER_COLOR = "rgba(210, 153, 34, 0.65)"

DRAW_TRIGGER = True

RAIL_WIDTH = 1
