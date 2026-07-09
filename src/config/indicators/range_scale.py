"""Dials for the range_scale indicator - the unit every threshold is measured in.

``WINDOW`` and ``MIN_BARS`` are in **bars, not minutes**, and that is the whole
point. Bar range grows as the square root of bar duration (measured on NQ:
``range ~ t^0.507``, r2 = 0.9996 from 30s to 1h), so N bars of any timeframe
carry comparable information. One window therefore serves every rung of the
ladder without being retuned per timeframe.

Nothing here is drawn. range_scale is a denominator, not a picture.
"""

from __future__ import annotations

ENABLED = True

# How many recent bars the estimate is taken over.
#
# Bar range is strongly persistent, which is the only reason a rolling estimate
# can work at all: on 5m NQ bars, the median range of the last N bars correlates
# with the median of the next N at 0.56 (N=6), 0.57 (N=30) and 0.65 (N=60). If
# range were independent bar to bar those numbers would be 0.00 and no adaptive
# threshold could exist. Longer windows are steadier and slower to react; 60 sits
# where the persistence has mostly arrived.
WINDOW = 60

# Publish nothing until this many bars have been seen. An estimate from three
# bars is not a rougher estimate - it is a different number, and every threshold
# downstream would be quietly wrong for the opening minutes of every replay.
MIN_BARS = 30
