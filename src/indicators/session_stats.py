"""The running session scorecard: range, net, travel, flow and POC, live.

One job: from the first bar of London or NY to now, accumulate everything
VPbreakout reads to judge a session's character - and publish nothing at all
for Asia, the halt, or before either session has begun.

Treats the whole session as one candle. ``session_range`` is its high minus
its low; ``session_net`` is close minus open; ``session_body_ratio`` /
``session_upwick_ratio`` / ``session_lowwick_ratio`` split that range the same
way a single candlestick would, and sum to 1.0.

Like everything else in the structure layer, ``session_range``, ``session_net``
and ``session_travel`` are measured in multiples of ``range_scale``, never in
points - range_scale is the only field in this whole codebase allowed to be
(``tests/test_fields.py`` enforces it). NQ's median bar range moved 3.17x
across 29 months; a session that is "big" in points in April is ordinary in
August, and the raw point count would silently mean something different every
few months. The ratio fields (``session_net_ratio`` and friends) need no such
conversion - they are already a fraction of the session's own range, and that
cancellation makes them regime-invariant by construction.

``session_travel`` sums every bar's own range - how far price actually walked,
bar to bar - so ``session_efficiency = range / travel`` says how much of that
walking was net progress: 1.0 is a straight line from open to now, and a small
number is a session that covered a lot of ground and went nowhere.

``session_dir_changes`` counts bar-to-bar close reversals - a counting
measure, dimensionless by construction, that reads how choppy the session was
with no points threshold to calibrate. ``session_high_at_ratio`` /
``session_low_at_ratio`` say how far into the session (as a fraction of bars
so far) each running extreme was set - early is a session that picked a side
and defended it.

Volume and delta need order flow; the POC needs volume at price. Both are NQT
only, and both are None on a bar file - the same honesty ``orderflow`` and
``profile`` already keep. It does not guess.

It refuses outside ``config.TRACKED_SESSIONS``. VPbreakout trades London and
NY only, and a "session so far" for Asia or the halt is a number nobody asked
for and a rule could accidentally read.
"""

from __future__ import annotations

import logging

from src.config.indicators import session_stats as cfg
from src.indicators.base import Indicator
from src.profile.store import Ladder
from src.profile.value_area import EmptyProfile, value_area

logger = logging.getLogger(__name__)

_NOTHING = {
    "session_range": None, "session_bars": None, "session_net": None,
    "session_net_ratio": None, "session_closed_ratio": None,
    "session_body_ratio": None, "session_upwick_ratio": None,
    "session_lowwick_ratio": None, "session_travel": None,
    "session_efficiency": None, "session_dir_changes": None,
    "session_high_at_ratio": None, "session_low_at_ratio": None,
    "session_volume": None, "session_delta": None,
    "session_poc": None, "session_poc_ratio": None,
}


class SessionStats(Indicator):
    """Publishes the running session scorecard, or nothing outside London/NY."""

    id = "session_stats"
    fields = tuple(_NOTHING)
    depends = ("sessions", "range_scale")

    about = {
        "session_range": ("x range_scale", "(session_high - session_low) / "
                          "range_scale, so far. None until range_scale itself "
                          "has warmed up."),
        "session_bars": ("count", "Bars seen since the session opened."),
        "session_net": ("x range_scale", "(close - session_open) / range_scale. "
                        "Signed: negative is a session that sold off."),
        "session_net_ratio": ("-1..+1", "session_net / session_range. How much of "
                              "the session's own range the net move actually "
                              "covered - direction and strength in one number."),
        "session_closed_ratio": ("0..1", "(close - session_low) / session_range. "
                                 "Where price sits right now inside the session's "
                                 "own range. Near 0 is at the low, near 1 at the high."),
        "session_body_ratio": ("0..1", "|session_net| / range, treating the whole "
                               "session as one candle. body + up-wick + low-wick "
                               "sum to 1."),
        "session_upwick_ratio": ("0..1", "(session_high - max(open, close)) / range."),
        "session_lowwick_ratio": ("0..1", "(min(open, close) - session_low) / range."),
        "session_travel": ("x range_scale", "Sum of every bar's own (high - low) "
                           "since the open, / range_scale - how far price actually "
                           "walked, not just where it ended up."),
        "session_efficiency": ("0..1", "session_range / session_travel. 1.0 is a "
                               "straight line from open to now; a small number is "
                               "a session that covered a lot of ground for little "
                               "net progress - the ratio companion to "
                               "session_dir_changes."),
        "session_dir_changes": ("count", "Times the close-to-close direction "
                                "flipped sign since the open. A counting measure: "
                                "how choppy the session read, with no points "
                                "threshold to calibrate."),
        "session_high_at_ratio": ("0..1", "How far into the session (by bar count) "
                                  "the running high was set. Near 0 is early - the "
                                  "high was made and defended."),
        "session_low_at_ratio": ("0..1", "The same, for the running low."),
        "session_volume": ("contracts", "Total volume since the session opened. "
                           "None on a bar file - use a tick-rebuilt dataset (NQT)."),
        "session_delta": ("contracts, signed", "Sum of buy_volume - sell_volume "
                          "since the session opened. None on a bar file, never a "
                          "proxy zero."),
        "session_poc": ("price", "The session's own point of control: the single "
                        "price with the most volume traded at it since the open. "
                        "None without volume at price (NQT + python -m src.cli.vap)."),
        "session_poc_ratio": ("0..1", "(session_poc - session_low) / session_range. "
                              "Where the market's fair price sits inside the range "
                              "it built to find it."),
    }

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._tracking = False
        self._clear()

    def _clear(self) -> None:
        self._open = self._high = self._low = self._close = None
        self._bars = 0
        self._travel = 0.0
        self._high_bar = self._low_bar = 0
        self._dir_changes = 0
        self._last_close: float | None = None
        self._last_sign: int | None = None
        self._volume: float | None = None
        self._delta: float | None = None
        self._ladder = Ladder()

    def update(self, event, upstream=None) -> dict:
        up = upstream or {}
        if up.get("session_new"):
            self._tracking = up.get("session") in cfg.TRACKED_SESSIONS
            self._clear()

        if not self._tracking:
            return dict(_NOTHING)

        self._observe(event)
        return self._publish(up.get("range_scale"))

    def _observe(self, event) -> None:
        o, h, lo, c = event.open, event.high, event.low, event.close
        self._bars += 1
        self._travel += h - lo

        # The bar count at which the running extreme was LAST (re)set, so a
        # later tie still credits the bar that most recently made it.
        if self._high is None or h >= self._high:
            self._high, self._high_bar = h, self._bars
        if self._low is None or lo <= self._low:
            self._low, self._low_bar = lo, self._bars

        if self._open is None:
            self._open = o
        self._close = c

        # A reversal, not merely a move: the first tick off a flat state sets
        # the running direction, it does not flip it.
        sign = 0 if self._last_close is None else (c > self._last_close) - (c < self._last_close)
        if sign != 0:
            if self._last_sign is not None and sign != self._last_sign:
                self._dir_changes += 1
            self._last_sign = sign
        self._last_close = c

        delta = getattr(event, "delta", None)
        if delta is not None:
            self._volume = (self._volume or 0.0) + (event.volume or 0.0)
            self._delta = (self._delta or 0.0) + delta

        vap = getattr(event, "vap", None)
        if vap is not None:
            prices, volume, buy = vap
            self._ladder.add(prices, volume, buy)

    def _publish(self, scale: float | None) -> dict:
        rng = self._high - self._low
        net = self._close - self._open
        row = dict(_NOTHING)
        row["session_bars"] = self._bars
        row["session_dir_changes"] = self._dir_changes
        row["session_volume"] = self._volume
        row["session_delta"] = self._delta

        # Ratios of the session's own range to itself - the range_scale unit
        # cancels out of them, so they need no conversion to be regime-invariant.
        if rng > 0:
            row["session_net_ratio"] = net / rng
            row["session_closed_ratio"] = (self._close - self._low) / rng
            row["session_body_ratio"] = abs(net) / rng
            row["session_upwick_ratio"] = (self._high - max(self._open, self._close)) / rng
            row["session_lowwick_ratio"] = (min(self._open, self._close) - self._low) / rng
        if self._travel > 0:
            row["session_efficiency"] = rng / self._travel
        row["session_high_at_ratio"] = self._high_bar / self._bars
        row["session_low_at_ratio"] = self._low_bar / self._bars

        # The absolute sizes DO need the conversion: range_scale is the only
        # field this codebase allows in points, so a session that is "big" in
        # April must not silently mean something different in August.
        if scale:
            row["session_range"] = rng / scale
            row["session_net"] = net / scale
            row["session_travel"] = self._travel / scale

        if self._ladder:
            prices, volume, _buy = self._ladder.arrays()
            try:
                poc, _val, _vah = value_area(prices, volume)
                row["session_poc"] = poc
                if rng > 0:
                    row["session_poc_ratio"] = (poc - self._low) / rng
            except EmptyProfile:
                pass
        return row
