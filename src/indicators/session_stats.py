"""The running session scorecard: range, net, flow, POC and phase, live.

One job: from the first bar of London or NY to now, accumulate everything
VPbreakout reads to judge a session's character - and publish nothing at all
for Asia, the halt, or before either session has begun.

Treats the whole session as one candle. ``session_range`` is its high minus
its low; ``session_net`` is close minus open. There is no body/wick split -
it would be three lines computed from the two already above it: given
``session_net_ratio`` and ``session_closed_ratio``, ``open_ratio =
closed_ratio - net_ratio`` always, and body/up-wick/low-wick fall straight out
of that as arithmetic on numbers already on the card. Publishing all five
would be the same two facts, told three extra times.

Like everything else in the structure layer, ``session_range`` and
``session_net`` are measured in multiples of ``range_scale``, never in points
- range_scale is the only field in this whole codebase allowed to be
(``tests/test_fields.py`` enforces it). NQ's median bar range moved 3.17x
across 29 months; a session that is "big" in points in April is ordinary in
August, and the raw point count would silently mean something different every
few months. The ratio fields (``session_net_ratio`` and friends) need no such
conversion - they are already a fraction of the session's own range, and that
cancellation makes them regime-invariant by construction.

**session_efficiency/session_dir_changes/session_travel do not exist here.**
They used to be computed open-to-now, and that silently failed on any session
with more than one character: a crash-then-base session measured
``efficiency 0.33``, the blend of a ~1.0 impulse and a ~0.1 consolidation,
describing neither. ``session_dir_changes`` had a second bug on top of the
blend - it is a monotonically growing COUNT, so it can never report that the
market just started trending, only that it has trended a cumulative amount
since open. Aggregates over a bimodal session do not return an error; they
return a plausible-looking number pointing the wrong way.

**session_efficiency_recent/_prior, session_range_ratio, session_volume_ratio
and session_dir_change_rate replace them**, all built on the SAME sliding
window pair: ``recent`` (the last config.RECENT_WINDOW_MINUTES) and ``prior``
(the config.RECENT_WINDOW_MINUTES before that), both floored at
config.RECENT_MIN_BARS bars, recomputed every bar - sliding, never tumbling,
because a fixed non-overlapping block reintroduces the exact blending bug at
an arbitrary cut point. N was measured, not guessed
(scratch/analysis/session_window_study.py; see config for the table).

These fields need NO range_scale conversion - a ratio of two windows of the
same unit cancels it, same as ``session_net_ratio`` does for the whole
session. range_scale's job (converting a magnitude so it survives a change of
volatility regime) is already done for session_range/session_net; the
recent/prior split exists for a DIFFERENT job entirely - noticing that the
session's character just changed - and normalizing twice would be solving a
problem that does not exist.

``session_dir_change_rate`` counts reversals only inside the recent window,
divided by its bar count - a rate, not a ratchet, so it can rise and fall as
the market's own choppiness does instead of only ever growing.

Volume needs order flow; the POC and the session's own volume profile need
volume at price. Both are NQT only, and both are None on a bar file - the
same honesty ``orderflow`` and ``profile`` already keep. It does not guess.

``session_delta_recent`` is delta over the same recent window, not since the
session opened - a cumulative sum across a session that changed character
does not average opposing regimes, it CANCELS them. A crash worth tens of
thousands of contracts of aggressive selling, followed by dip-buying at the
lows, nets to a small number that reads as "no conviction" when the opposite
happened twice. Delta is signed; unlike ``session_volume`` (unsigned, and
genuinely additive - "566K contracts traded this session" stays true no
matter how the session turned), a running sum of a signed quantity is only
honest within one regime.

The profile itself folds bars into the same live tick-grid accumulator
(``profile.store.Ladder``) that ``indicators/profile.py``'s developing range
uses - one fold, shared - and bins it the same way: ``range_scale /
config.BINS_PER_SCALE`` wide, so the histogram's shape is comparable between a
quiet hour and a loud one rather than drawing the clock.

It refuses outside ``config.TRACKED_SESSIONS``. VPbreakout trades London and
NY only, and a "session so far" for Asia or the halt is a number nobody asked
for and a rule could accidentally read.

Deliberately NOT coupled to ``indicators/regime.py`` - not considered complete
or validated, and its cutoffs were tuned for a different purpose. This
indicator stays standalone; ``range_scale`` is its only dependency besides
``sessions``.
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass

from src.config.indicators import session_stats as cfg
from src.indicators.base import Indicator
from src.profile import store
from src.profile.store import Ladder
from src.profile.value_area import EmptyProfile, value_area

logger = logging.getLogger(__name__)

_NOTHING = {
    "session_range": None, "session_bars": None, "session_net": None,
    "session_net_ratio": None, "session_closed_ratio": None,
    "session_efficiency_recent": None, "session_efficiency_prior": None,
    "session_range_ratio": None, "session_volume_ratio": None,
    "session_dir_change_rate": None,
    "session_high_at_ratio": None, "session_low_at_ratio": None,
    "session_volume": None, "session_delta_recent": None,
    "session_poc": None, "session_poc_ratio": None,
    "session_val": None, "session_vah": None, "session_bins": None,
    "session_from_time": None, "session_to_time": None,
}


@dataclass
class _Bar:
    """One bar's worth of what the recent/prior windows need. Small on purpose:
    these windows hold a handful of bars, sliced and summed fresh every bar."""

    ts: int
    high: float
    low: float
    range: float
    volume: float
    delta: float | None
    reversal: bool


def _window_stats(entries: list[_Bar]) -> dict | None:
    """(range, travel, efficiency) over a window, or None if it is too thin.

    ``range`` is the WINDOW's own high-to-low span - a single number for the
    whole window, a rolling max minus a rolling min - never a sum of the bars
    in it. ``travel`` sums each bar's OWN (high - low). Conflating the two
    (summing per-bar ranges for both) would silently turn efficiency into a
    different, wrong quantity.
    """
    if len(entries) < cfg.RECENT_MIN_BARS:
        return None
    rng = max(e.high for e in entries) - min(e.low for e in entries)
    travel = sum(e.range for e in entries)
    return {
        "range": rng,
        "efficiency": rng / travel if travel > 0 else None,
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
                                 "own range. Near 0 is at the low, near 1 at the high. "
                                 "No separate body/wick split is published: given this "
                                 "and session_net_ratio, open_ratio = closed_ratio - "
                                 "net_ratio always, and body/up-wick/low-wick are "
                                 "arithmetic on those two - not a third fact."),
        "session_efficiency_recent": ("0..1", "range / travel over the last "
                                      "config.RECENT_WINDOW_MINUTES (floored at "
                                      "RECENT_MIN_BARS bars). 1.0 is a straight line; "
                                      "a small number is chop. Needs no range_scale - "
                                      "the ratio is already dimensionless."),
        "session_efficiency_prior": ("0..1", "The same measurement, one window "
                                     "further back - the window BEFORE session_"
                                     "efficiency_recent, same width, not overlapping. "
                                     "Comparing this against session_efficiency_recent "
                                     "is how a phase change is caught: efficiency_prior "
                                     "high then efficiency_recent low is an impulse "
                                     "handing off to a base."),
        "session_range_ratio": ("ratio", "recent window's (high-low) span divided by "
                                "the prior window's. << 1 is contraction - the "
                                "classic tell that a base is forming, not merely "
                                "that the market went quiet."),
        "session_volume_ratio": ("ratio", "Sum of volume in the recent window "
                                 "divided by the prior window's. Declining volume "
                                 "through a would-be base is the tell that "
                                 "continuation, not reversal, is next."),
        "session_dir_change_rate": ("0..1", "Close-to-close direction reversals in "
                                   "the recent window, / bars in that window. A RATE, "
                                   "not the count session_dir_changes used to be - a "
                                   "monotonic count can only ever grow, so it can never "
                                   "report that the market just started trending; a "
                                   "rate can fall as cleanly as it rises."),
        "session_high_at_ratio": ("0..1", "How far into the session (by bar count) "
                                  "the running high was set. Near 0 is early - the "
                                  "high was made and defended."),
        "session_low_at_ratio": ("0..1", "The same, for the running low."),
        "session_volume": ("contracts", "Total volume since the session opened. "
                           "Unsigned and genuinely additive, so cumulative is honest "
                           "here in a way it is not for delta. None on a bar file - "
                           "use a tick-rebuilt dataset (NQT)."),
        "session_delta_recent": ("contracts, signed", "Sum of buy_volume - sell_volume "
                                 "over the last config.RECENT_WINDOW_MINUTES, NOT since "
                                 "the session opened. A cumulative sum across a session "
                                 "that changed character cancels its own regimes rather "
                                 "than averaging them - a crash's aggressive selling and "
                                 "the dip-buying that followed it net to a small number "
                                 "that reads as indecision when both moves had real "
                                 "conviction. None on a bar file, never a proxy zero; "
                                 "None until RECENT_MIN_BARS have been seen."),
        "session_poc": ("price", "The session's own point of control: the single "
                        "price with the most volume traded at it since the open. "
                        "None without volume at price (NQT + python -m src.cli.vap); "
                        "None until range_scale has warmed up - the bins it sizes; "
                        "and None while the chart's Profile toggle is off, the same "
                        "switch `profile` itself uses - volume at price is a per-bar "
                        "store lookup, and the switch exists so a plain browse never "
                        "pays for it unasked."),
        "session_poc_ratio": ("0..1", "(session_poc - session_low) / session_range. "
                              "Where the market's fair price sits inside the range "
                              "it built to find it."),
        "session_val": ("price", "Value area low: the bottom of the contiguous band "
                        "around the POC holding config.profile.VALUE_AREA of the "
                        "session's volume so far."),
        "session_vah": ("price", "Value area high: the top of that same band."),
        "session_bins": ("payload", "The session's own histogram so far: "
                         "[price, volume, buy_volume] per bin, bins range_scale / "
                         "BINS_PER_SCALE wide. The chart draws it; nothing else "
                         "should read it - five readings already say what it says."),
        "session_from_time": ("epoch seconds, UTC", "Close time of the session's "
                              "first bar - where the profile drawing anchors."),
        "session_to_time": ("epoch seconds, UTC", "Close time of the current bar - "
                            "the profile's right edge, moving every bar."),
    }

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._tracking = False
        self._clear()

    def _clear(self) -> None:
        self._open = self._high = self._low = self._close = None
        self._bars = 0
        self._high_bar = self._low_bar = 0
        self._last_close: float | None = None
        self._last_sign: int | None = None
        self._volume: float | None = None
        self._ladder = Ladder()
        self._first_ts: int | None = None
        self._last_ts: int | None = None
        # Holds enough bars for BOTH the recent and prior windows, sliced by
        # timestamp fresh each publish - small (a handful of bars), so slicing
        # beats maintaining incremental rolling max/min for no real cost.
        self._window: deque[_Bar] = deque()

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
        ts = int(event.ts.timestamp())
        if self._first_ts is None:
            self._first_ts = ts
        self._last_ts = ts
        self._bars += 1

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
        reversal = (sign != 0 and self._last_sign is not None and sign != self._last_sign)
        if sign != 0:
            self._last_sign = sign
        self._last_close = c

        delta = getattr(event, "delta", None)
        if delta is not None:
            self._volume = (self._volume or 0.0) + (event.volume or 0.0)

        self._window.append(_Bar(ts=ts, high=h, low=lo, range=h - lo,
                                 volume=event.volume, delta=delta, reversal=reversal))
        self._evict_window(ts)

        vap = getattr(event, "vap", None)
        if vap is not None:
            prices, volume, buy = vap
            self._ladder.add(prices, volume, buy)

    def _evict_window(self, ts: int) -> None:
        """Drop what is both older than 2 windows' worth of time AND spare.

        Both conditions, never one - the window must never shrink below what
        both the recent and prior slices need, however little time they span
        (the same rule range_scale's own window keeps).
        """
        floor = 2 * cfg.RECENT_MIN_BARS
        horizon = ts - 2 * cfg.RECENT_WINDOW_MINUTES * 60
        while len(self._window) > floor and self._window[0].ts <= horizon:
            self._window.popleft()

    def _windows(self, now: int) -> tuple[list[_Bar], list[_Bar]]:
        """(recent, prior): two adjacent, non-overlapping slices of the window."""
        recent_cutoff = now - cfg.RECENT_WINDOW_MINUTES * 60
        prior_cutoff = now - 2 * cfg.RECENT_WINDOW_MINUTES * 60
        recent = [e for e in self._window if e.ts > recent_cutoff]
        prior = [e for e in self._window if prior_cutoff < e.ts <= recent_cutoff]
        return recent, prior

    def _publish(self, scale: float | None) -> dict:
        rng = self._high - self._low
        net = self._close - self._open
        row = dict(_NOTHING)
        row["session_bars"] = self._bars
        row["session_volume"] = self._volume

        # Ratios of the session's own range to itself - the range_scale unit
        # cancels out of them, so they need no conversion to be regime-invariant.
        if rng > 0:
            row["session_net_ratio"] = net / rng
            row["session_closed_ratio"] = (self._close - self._low) / rng
        row["session_high_at_ratio"] = self._high_bar / self._bars
        row["session_low_at_ratio"] = self._low_bar / self._bars

        # The absolute sizes DO need the conversion: range_scale is the only
        # field this codebase allows in points, so a session that is "big" in
        # April must not silently mean something different in August.
        if scale:
            row["session_range"] = rng / scale
            row["session_net"] = net / scale

        self._publish_windows(row)

        if self._ladder and scale:
            row["session_from_time"] = self._first_ts
            row["session_to_time"] = self._last_ts
            bin_size = scale / cfg.BINS_PER_SCALE
            prices, volume, buy = store.rebin(*self._ladder.arrays(), bin_size)
            try:
                poc, val, vah = value_area(prices, volume)
                row["session_poc"] = poc
                row["session_val"] = val
                row["session_vah"] = vah
                if rng > 0:
                    row["session_poc_ratio"] = (poc - self._low) / rng
                row["session_bins"] = [[float(p), int(v), int(b)]
                                       for p, v, b in zip(prices, volume, buy)]
            except EmptyProfile:
                pass
        return row

    def _publish_windows(self, row: dict) -> None:
        """The recent/prior phase-detection fields - all dimensionless already."""
        recent, prior = self._windows(self._last_ts)
        recent_stats = _window_stats(recent)
        prior_stats = _window_stats(prior)

        if recent_stats:
            row["session_efficiency_recent"] = recent_stats["efficiency"]
            row["session_dir_change_rate"] = (
                sum(1 for e in recent if e.reversal) / len(recent))

            delta_entries = [e for e in recent if e.delta is not None]
            if len(delta_entries) >= cfg.RECENT_MIN_BARS:
                row["session_delta_recent"] = sum(e.delta for e in delta_entries)

        if prior_stats:
            row["session_efficiency_prior"] = prior_stats["efficiency"]

        if recent_stats and prior_stats:
            if prior_stats["range"] > 0:
                row["session_range_ratio"] = recent_stats["range"] / prior_stats["range"]
            recent_vol = sum(e.volume for e in recent)
            prior_vol = sum(e.volume for e in prior)
            if prior_vol > 0:
                row["session_volume_ratio"] = recent_vol / prior_vol
