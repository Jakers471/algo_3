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

# Per-session accents, matching the chart's session rules.
SESSION_COLORS = {
    "Asia": "#58a6ff",
    "London": "#d29922",
    "NY": "#3fb950",
}
HALT_COLOR = MUTED

FONT_FAMILY = "JetBrains Mono, Consolas, Courier New, monospace"
FONT_SIZE_PT = 10
ROW_HEIGHT = 22

# Follow the newest row unless the user has scrolled away from the bottom.
# Slack in pixels: a scrollbar parked "at the bottom" is rarely exactly there.
FOLLOW_SLACK_PX = 4
