"""Dials for the sessions indicator.

One job: hold what the sessions indicator publishes and what its drawing looks
like. The session WINDOWS themselves are market truth, not an indicator
preference, so they live in ``config/session.py`` and are read from there - this
file never redefines them.

Style lives here rather than in the frontend because the backend emits drawing
instructions and the chart only renders them. One source for what a session is,
one source for how it looks.
"""

from __future__ import annotations

ENABLED = True

# The dashed vertical rule dropped at each session open, and its label.
LINE_COLORS = {
    "Asia":   "rgba(88, 166, 255, 0.70)",   # blue
    "London": "rgba(210, 153, 34, 0.70)",   # amber
    "NY":     "rgba(63, 185, 80, 0.70)",    # green
}
LABEL_COLORS = {
    "Asia":   "rgba(126, 187, 255, 0.95)",
    "London": "rgba(227, 179, 65, 0.95)",
    "NY":     "rgba(86, 211, 100, 0.95)",
}

DRAW_BOUNDARIES = True   # the dashed rule + label at each session open
