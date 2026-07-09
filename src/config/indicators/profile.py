"""Dials for the volume profile - the developing range, and the ones it left behind.

There is one range now, and it is the **developing** one: from the last confirmed
swing to the current bar. It grows every bar, it never looks ahead, and it always
exists - including immediately after a break of structure, when there is no
complete high-low box at all (about half of all bars).

When a swing confirms, that range is finished. Its profile freezes, keeps its own
price band and its own bar span, and stays on the chart; a new developing profile
starts from the swing. So the chart carries a row of profiles, one per structure,
each anchored to the range it describes.

Two earlier modes are gone. "leg" was this profile, frozen, and discarded instead
of kept. "box" clipped it to the price band between the last two confirmed swings
- a leg is an interval in TIME and a box an interval in PRICE, so they really did
differ, but the clip threw away the volume that traded outside the band, which is
exactly the volume a break of structure is made of.

Bins are sized in ``range_scale``, never in points. A profile binned in ticks has
four times as many bins at the New York open as it has overnight, so the same
market would look spiky in one hour and smooth in the next - the histogram would
be drawing the clock rather than the market.
"""

from __future__ import annotations

ENABLED = True

# The base bars whose one-tick histograms are summed. Built by src.cli.vap.
BASE_TIMEFRAME = "30s"

# Bin width = range_scale / BINS_PER_SCALE. Eight puts roughly one bin per eighth
# of a typical bar, which keeps a profile near 30-60 bins: enough shape to read,
# few enough to send in a snapshot row.
BINS_PER_SCALE = 8

# How many finished profiles stay on the chart behind the developing one.
#
# They are REDRAWN as a group on every bar rather than accumulated as events. A
# 5,000-bar browse window contains about ninety swings, and drawing each of their
# histograms as it went would put nine thousand segments and megabytes of payload
# on the wire for a picture nobody can read.
MAX_CLOSED = 6

# --- drawing ----------------------------------------------------------------
DRAW = True
DRAW_CLOSED = True

# Each bin is a horizontal bar anchored at its range's right edge and growing
# left, the heaviest reaching this many PIXELS.
#
# Pixels, not seconds. A bin's left end at an interpolated timestamp has no x
# coordinate: lightweight-charts maps a time to a coordinate by looking it up in
# the series, and returns null for a moment no bar occupies. The primitive then
# skips the whole polyline - so every bin was silently invisible. The anchor is a
# real bar; the length is an offset from it.
MAX_WIDTH_PX = 170
CLOSED_WIDTH_PX = 110

# Bought at the ask, and sold at the bid. The same green and red as the delta
# strip, because it is the same measurement seen against price instead of time.
BUY_COLOR = "rgba(38, 166, 154, 0.55)"
SELL_COLOR = "rgba(239, 83, 80, 0.55)"

# A finished profile is history. Dimmer, so the developing one reads as the live
# thing it is.
CLOSED_BUY_COLOR = "rgba(38, 166, 154, 0.26)"
CLOSED_SELL_COLOR = "rgba(239, 83, 80, 0.26)"

# The point of control: the price that traded most. Bright, because it is the one
# line in a profile a trader actually looks for.
POC_COLOR = "#d29922"
CLOSED_POC_COLOR = "rgba(210, 153, 34, 0.55)"
# The band holding VALUE_AREA of the volume (see config/profile.py).
VALUE_AREA_COLOR = "rgba(210, 153, 34, 0.45)"

BIN_HEIGHT = 1
POC_WIDTH = 2
