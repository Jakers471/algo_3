"""Dials for the MA indicator - a short list of named moving averages.

Unlike `ribbon` (a fan of 32 evenly-spaced SMAs, coloured by slope, meant to be
read as one shape), this is a small explicit set - "the 50" or "the 50 and the
200" - each independently switchable and each its own fixed colour, the way a
trader actually asks for named averages rather than a fan.

Add a line by adding an entry to LINES; turn one off by flipping its own
`enabled` flag. No change to the indicator or the chart is needed either way.
"""

from __future__ import annotations

ENABLED = True

# period, whether it runs, and the colour its line is stroked in. Order here is
# the order the lines are computed and drawn in.
LINES = (
    {"period": 50, "enabled": True, "color": "#e8a33d"},
    {"period": 100, "enabled": True, "color": "#58a6ff"},
    {"period": 200, "enabled": True, "color": "#bc8cff"},
)

# The lines actually running, derived once so the indicator and the drawing
# layer read the same list in the same order.
ACTIVE = tuple(line for line in LINES if line["enabled"])

# --- drawing ----------------------------------------------------------------
DRAW = True

WIDTH = 1
