"""Dials for the desktop snapshot table.

One job: hold what the table looks like and how much it remembers. The columns
themselves are not configured here - they are whatever the replay session says
its fields are, so adding an indicator adds a column with no edit to this file.
"""

from __future__ import annotations

# Where the chart server lives. The table is a second subscriber to the same
# replay session, not a second source of truth.
SERVER_URL = "http://127.0.0.1:8765"

# --- memory -----------------------------------------------------------------
# Rows kept in the table. A long replay would otherwise grow without bound.
# The oldest are dropped, exactly as the chart trims its bar buffer.
MAX_ROWS = 20_000

# Milliseconds between drains of the inbound queue into the view. At 4x a bar
# lands every 125ms, so this is comfortably ahead of the data.
DRAIN_INTERVAL_MS = 40

# --- theme (matches frontend/chart/css/chart.css) ---------------------------
BG = "#0d1117"
PANEL = "#10151c"
LINE = "#1c2128"
TEXT = "#c9d1d9"
MUTED = "#7d8590"
ACCENT = "#58a6ff"
UP = "#26a69a"
DOWN = "#ef5350"
SELECTION = "#1f6feb40"

# The row you are hunting: price closed against its own order flow.
ABSORPTION = "#d29922"
ABSORPTION_ROW = "#1d1a10"   # a dim wash behind the whole row, not a highlight

# Per-session accents, matching the chart's session rules.
SESSION_COLORS = {
    "Asia": "#58a6ff",
    "London": "#d29922",
    "NY": "#3fb950",
}
HALT_COLOR = MUTED

# One hue per indicator, so a column always says where its number came from.
#
# Columns are grouped by their producer already; the colour makes the grouping
# survive a horizontal scroll, when the block's name has slid off the screen and
# a header reading "retrace" tells you nothing about which file computed it.
# `python -m src.cli.fields` is the same map in text, with the source and the
# config file beside each name.
#
# The colour lives on the HEADER, never on a cell: a cell's colour already means
# something (green up, red down, grey absent) and two meanings on one pixel is
# one meaning too many.
GROUP_COLORS = {
    "bar": "#7d8590",
    "sessions": "#58a6ff",
    "orderflow": "#a371f7",
    "absorption": "#d29922",
    "range_scale": "#39c5cf",
    "swing": "#3fb950",
    "legs": "#7d8590",
    "breaks": "#ef5350",
    "profile": "#db6d28",
    "ribbon": "#5691c8",
}
GROUP_FALLBACK = TEXT

# A hairline down the left of each block's first column, so the eye finds the
# seams even where two blocks happen to share a hue.
GROUP_SEPARATOR = "#30363d"

FONT_FAMILY = "JetBrains Mono, Consolas, Courier New, monospace"
FONT_SIZE_PT = 10
ROW_HEIGHT = 22

# Columns are sized to their contents, but a long HEADER ("absorption side",
# "session new") then reserves width for a word rather than for the values
# underneath it, and the row spreads across the screen with nothing in it.
COLUMN_MAX_PX = 130

# Follow the newest row unless the user has scrolled away from the bottom.
# Slack in pixels: a scrollbar parked "at the bottom" is rarely exactly there.
FOLLOW_SLACK_PX = 4

# --- reconnecting -----------------------------------------------------------
# A dropped stream is retried with a growing delay. Never retry immediately: a
# retired session closes the connection cleanly, which looks identical to a
# healthy close, and a zero-delay retry becomes a reconnect storm.
RECONNECT_DELAY_S = 0.5
RECONNECT_DELAY_MAX_S = 5.0

# When the session we were watching disappears, look for the one that replaced
# it. Switching timeframe on the chart retires a session and starts another;
# the table should follow, not die.
ADOPT_NEW_SESSION = True
