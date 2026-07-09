"""Dials for the swing indicator - where the structure points land.

``RETRACE`` is the only real dial, and it is expressed in multiples of
``range_scale``, never in points. A swing is confirmed when price pulls back
that far from the running extreme.

**It chooses density, not which timeframe dominates.** Raising it thins every
rung at once. Swings per NY session, measured over 658 sessions of NQ with these
very indicators:

    RETRACE      30s      3m     15m    | rung spacing
       1.0     279.4    42.5    8.80    |  /6.6  /4.8
       1.5     166.0    27.1    5.90    |  /6.1  /4.6
       2.0     107.5    18.5    4.00    |  /5.8  /4.6
       3.0      55.2     9.9    2.10    |  /5.6  /4.7
       4.0      34.8     6.1    1.30    |  /5.7  /4.7
       6.0      18.4     2.8    0.62    |  /6.5  /4.5
      10.0       8.1     1.2    0.25    |  /6.9  /4.7

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
RETRACE = 5.0

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
