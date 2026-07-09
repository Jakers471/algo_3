"""Dials for the volume profile indicator - which range it covers, and how it draws.

``MODE`` is the question Jake wanted to answer by looking:

    "developing"  every bar since the last confirmed swing, up to NOW.
                  Grows each bar. Always exists, even right after a break.

    "leg"         frozen between two confirmed swings. A historical object,
                  known only once the second swing confirms.

    "box"         the same time range as "developing", but CLIPPED to the price
                  band between the standing high and the standing low.

A leg is an interval in TIME. A box is an interval in PRICE. They are not the
same range: measured on a real leg, price traded 90 points BELOW the swing low
the leg started from - because once a low confirms, `swing` hunts a high and
nothing stops price falling under it. "developing" and "box" therefore cover the
identical bars and different prices; "leg" covers different bars entirely.

Bins are sized in ``range_scale``, never in points. A profile binned in ticks has
four times as many bins at the New York open as it has overnight, so the same
market looks spiky in one hour and smooth in the next - the histogram would be
drawing the clock, not the market.
"""

from __future__ import annotations

ENABLED = True

# "developing" | "leg" | "box" | "off". The chart's toolbar overrides this per
# request; this is what a plain overlay call gets.
MODE = "developing"

# The base bars whose one-tick histograms are summed. Built by src.cli.vap.
BASE_TIMEFRAME = "30s"

# Bin width = range_scale / BINS_PER_SCALE. Eight puts roughly one bin per eighth
# of a typical bar, which keeps a session-long profile near 30-60 bins - enough
# shape to read, few enough to send in a snapshot row.
BINS_PER_SCALE = 8

# --- drawing ----------------------------------------------------------------
DRAW = True

# Each bin is a horizontal bar drawn INSIDE its own range, anchored at the right
# edge and growing left. Its length is this share of the range's width at the
# heaviest bin, so a profile never escapes the structure it describes.
MAX_WIDTH = 0.45

# Bought at the ask, and sold at the bid. The same green and red as the delta
# strip, because it is the same measurement seen against price instead of time.
BUY_COLOR = "rgba(38, 166, 154, 0.55)"
SELL_COLOR = "rgba(239, 83, 80, 0.55)"

# The point of control: the price that traded most. Bright, because it is the
# one line in the profile that a trader will actually look for.
POC_COLOR = "#d29922"
# The band holding VALUE_AREA of the volume (see config/profile.py).
VALUE_AREA_COLOR = "rgba(210, 153, 34, 0.45)"

BIN_HEIGHT = 1
POC_WIDTH = 2
