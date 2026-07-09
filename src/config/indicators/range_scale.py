"""Dials for the range_scale indicator - the unit every threshold is measured in.

The window is measured in **minutes of market time**, with a floor on how many
bars it must contain. Both are floors: the ruler looks back at least
``WINDOW_MINUTES``, and holds at least ``MIN_BARS`` bars, whichever demands more.

It used to be counted in bars alone, and that was wrong. The justification was
that bar range grows as the square root of bar duration (``range ~ t^0.507``,
r2 = 0.9996 from 30s to 1h), so N bars of any timeframe carry comparable
information. That is true of a bar's *size*. It says nothing about *when* the bar
happened - and volatility runs on the wall clock. A 15m NQ bar at the New York
open is 4.5x the size of one at 04:00 UTC.

So sixty bars was thirty minutes of memory on the 30s rung and **fifteen hours**
on the 15m rung, where it averaged most of the daily cycle. At the open the ruler
still remembered the quiet night and read 20 points when bars were really 57, and
a configured ``RETRACE`` of 6.0 became an effective 2.1 - while at 04:00 it became
13.3. Same file, same number, two different systems.

What actually drives the error is the window's WALL-CLOCK length; shorter is
always more accurate and always jitterier. Counted in minutes, every rung
remembers the same slice of the day. Mean error in effective RETRACE, against the
6.0 that was set:

                     30s        3m       15m     ladder
    60 bars         0.45      1.37      2.62       4.43   (the old rule)
    30 minutes      0.45      0.36      0.83       1.64   (this rule)
    120 minutes     1.25      1.02      0.83       3.10

Note the 120-minute row. It was the obvious fix and it is worse than useless on
the 30s rung, where sixty bars had *already* been thirty minutes. A longer window
there would have traded accuracy away for steadiness nobody asked for. The number
below is 30 for that reason and not because two hours sounded right.

Nothing here is drawn. range_scale is a denominator, not a picture.
"""

from __future__ import annotations

ENABLED = True

# How far back the ruler looks, in minutes of MARKET time - the timestamps on the
# events, never the wall clock, so a replay and a backtest measure exactly what
# the live feed would have.
#
# Shorter is more accurate and less steady, monotonically, with no knee to find.
# 30 minutes is the shortest that leaves the 30s rung a 60-bar sample (jitter 1.1%)
# while cutting the 15m rung's error by two thirds. Fifteen minutes would score
# better still (ladder 1.39) and doubles the jitter on every rung.
#
# The jitter this buys is visible: the chart's trigger line moves ~7% per bar on
# 15m, against ~1% before. If that ever matters more than the accuracy, the answer
# is NOT a longer window - it is to divide out the daily volatility profile, which
# is the only way to hold both (mean error 0.19 at the old steadiness). See
# scratch/analysis/seasonality_report.py.
WINDOW_MINUTES = 30

# The floor on sample size, and the same number that gates publishing at all.
#
# A median needs bars to be a median of. Thirty minutes is 60 bars on the 30s rung
# and 10 on the 3m rung - but only 2 on 15m and none at all on 1h, and the median
# of two numbers is their mean, which is not what was asked for. So the window
# never holds fewer than this many bars, however little time they span. On 15m and
# coarser this floor, not WINDOW_MINUTES, is what sets the memory.
#
# It is also what carries the ruler across the maintenance halt and the weekend,
# when thirty minutes of market time contains nothing at all.
#
# It gates publishing for the same reason: an estimate from three bars is not a
# rougher estimate, it is a different number, and every threshold downstream would
# be quietly wrong for the opening minutes of every replay.
MIN_BARS = 8
