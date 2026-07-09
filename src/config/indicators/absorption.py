"""Dials for the absorption indicator.

One job: hold what counts as absorption and how the chart marks it. The
thresholds are deliberately permissive by default - absorption is a *fact about
the bar* (it closed against its own order flow), not yet a claim that the fact
predicts anything. Tighten these once the rows tell you which ones matter.
"""

from __future__ import annotations

ENABLED = True

# Ignore bars whose disagreement is trivially small. 0 means "any disagreement",
# which is what was measured: 17.9% of bars close against their net order flow.
MIN_ABS_DELTA = 0.0

# Ignore thin bars, where a handful of contracts can flip the sign of delta.
MIN_VOLUME = 0.0

# Require the disagreement to be a real share of the bar's volume. 0.0 disables.
# e.g. 0.05 = delta must be at least 5% of the bar's volume.
MIN_DELTA_RATIO = 0.0

# --- drawing ----------------------------------------------------------------
# Off by default: a dot on one bar in five is noise on the candles, not signal.
# The field is still published, so the table shows it and the brain can read it.
DRAW_MARKERS = False

# Buyers absorbed the sellers: price rose on net selling. Marked below the bar,
# because the interest is underneath it.
BUY_ABSORPTION_COLOR = "#26a69a"
# Sellers absorbed the buyers: price fell on net buying. Marked above.
SELL_ABSORPTION_COLOR = "#ef5350"

MARKER_SHAPE = "circle"
