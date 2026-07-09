"""Where volume traded inside a structure: the profile, its POC and its value area.

One job: accumulate volume at price over the range the configured ``MODE`` names,
and publish the point of control, the value area, and the binned histogram itself.

**Three ranges, and they are genuinely different objects.**

``developing`` runs from the last confirmed swing to now. It grows every bar, it
never looks ahead, and it always exists - including immediately after a break of
structure, when there is no complete box at all (about half of all bars).

``leg`` is frozen between two confirmed swings. It is history, and like every leg
it is known only on the bar that confirmed its far end, never on the bar that
made it.

``box`` runs from the *previous* confirmed swing to now, and clips the histogram
to the price band between the last confirmed high and the last confirmed low.

That clip is the whole distinction, and it is not cosmetic. A leg is an interval
in TIME; a box is an interval in PRICE. Measured on a real leg: it began at a
swing low of 27,666.75 and its bars traded down to 27,576 - ninety points below
its own starting low - because once a low confirms, ``swing`` turns to hunting a
high and nothing prevents price falling beneath it. Those ninety points of volume
are in the leg and outside the box.

Note the band must be the two CONFIRMED swings, not ``swing``'s rails. One rail
is provisional - the running extreme since the last confirmation - so it contains
every bar of the developing range by construction, and clipping to it would clip
nothing at all.

**It refuses on bars with no volume at price.** Bar files record total volume and
a high and a low; they do not record where between them the contracts changed
hands, and no transformation recovers it. Fed those, this raises ``Unavailable``.
It does not spread the volume across the range - a profile drawn from that would
be a picture of the assumption, not of the market.

Bins are ``range_scale / BINS_PER_SCALE`` wide, never a fixed number of points,
so the histogram's shape is comparable between a quiet hour and a loud one.
"""

from __future__ import annotations

import logging
from collections import deque

import numpy as np

from src.config.indicators import profile as cfg
from src.indicators.base import Indicator, Unavailable
from src.profile import store
from src.profile.value_area import EmptyProfile, value_area

logger = logging.getLogger(__name__)

DEVELOPING, LEG, BOX = "developing", "leg", "box"

_NOTHING = {"profile_poc": None, "profile_val": None, "profile_vah": None,
            "profile_from_time": None, "profile_to_time": None, "profile_volume": None,
            "profile_bins": None}


class Profile(Indicator):
    """Volume at price over the developing range, the last leg, or the box."""

    id = "profile"
    fields = ("profile_poc", "profile_val", "profile_vah",
              "profile_from_time", "profile_to_time", "profile_volume", "profile_bins")
    depends = ("range_scale", "swing")

    def __init__(self, mode: str = None) -> None:
        self.mode = mode or cfg.MODE
        if self.mode not in (DEVELOPING, LEG, BOX):
            raise ValueError(f"unknown profile mode {self.mode!r}")
        self.reset()

    def reset(self) -> None:
        # One entry per bar: (ts, prices, volume, buy). Kept per bar rather than
        # pre-summed so a confirmation can split the run exactly at the bar that
        # MADE the swing, not at the later bar that proved it.
        self._bars: deque = deque()          # since the last confirmed swing
        self._prev_bars: list = []           # the leg before it
        self._leg: tuple | None = None       # that leg, already summed
        self._leg_span: tuple | None = None
        self._swings: deque = deque(maxlen=2)   # the last two confirmed (price, time)

    def update(self, event, upstream=None) -> dict:
        up = upstream or {}
        scale = up.get("range_scale")
        if scale is None:
            raise Unavailable("profile needs range_scale to size its bins")
        if event.vap is None:
            raise Unavailable(
                "this bar carries no volume at price; use a tick-rebuilt dataset "
                "and run: python -m src.cli.vap")

        ts = int(event.ts.timestamp())
        prices, volume, buy = event.vap
        self._bars.append((ts, prices, volume, buy))

        if up.get("swing"):
            self._freeze(int(up["swing_time"]))
            self._swings.append((float(up["swing_price"]), int(up["swing_time"])))

        return self._publish(scale, ts)

    # --- state ---------------------------------------------------------------

    def _freeze(self, swing_time: int) -> None:
        """A swing confirmed. Everything up to the bar that MADE it is a leg."""
        inside = [b for b in self._bars if b[0] <= swing_time]
        after = [b for b in self._bars if b[0] > swing_time]
        if inside:
            self._leg = _merge(inside)
            self._leg_span = (inside[0][0], inside[-1][0])
            self._prev_bars = inside
        self._bars = deque(after)

    def _publish(self, scale: float, now: int) -> dict:
        if self.mode == LEG:
            if self._leg is None:
                return dict(_NOTHING)
            return self._summarise(*self._leg, self._leg_span, scale)

        if self.mode == BOX:
            # The band is the last two CONFIRMED swings - one high, one low,
            # because swings alternate. Before two exist there is no box, which
            # is a fact about the structure and not a failure to compute one.
            if len(self._swings) < 2:
                return dict(_NOTHING)
            band = sorted(p for p, _ in self._swings)
            bars = self._prev_bars + list(self._bars)
            if not bars:
                return dict(_NOTHING)
            prices, volume, buy = _merge(bars)
            inside = (prices >= band[0]) & (prices <= band[1])
            return self._summarise(prices[inside], volume[inside], buy[inside],
                                   (bars[0][0], now), scale)

        if not self._bars:
            return dict(_NOTHING)
        prices, volume, buy = _merge(self._bars)
        return self._summarise(prices, volume, buy, (self._bars[0][0], now), scale)

    def _summarise(self, prices, volume, buy, span, scale) -> dict:
        bin_size = scale / cfg.BINS_PER_SCALE
        prices, volume, buy = store.rebin(prices, volume, buy, bin_size)
        try:
            poc, val, vah = value_area(prices, volume)
        except EmptyProfile:
            return dict(_NOTHING)

        return {
            "profile_poc": poc,
            "profile_val": val,
            "profile_vah": vah,
            "profile_from_time": span[0],
            "profile_to_time": span[1],
            "profile_volume": int(volume.sum()),
            # Flat triples, so the row stays JSON and the chart draws without
            # knowing what a value area is.
            "profile_bins": [[float(p), int(v), int(b)]
                             for p, v, b in zip(prices, volume, buy)],
        }


def _merge(bars) -> tuple:
    """Sum several bars' one-tick histograms into one. Exact; nothing is binned."""
    prices = np.concatenate([b[1] for b in bars])
    volume = np.concatenate([b[2] for b in bars])
    buy = np.concatenate([b[3] for b in bars])

    unique, inverse = np.unique(prices, return_inverse=True)
    v = np.zeros(len(unique), dtype=np.int64)
    b = np.zeros(len(unique), dtype=np.int64)
    np.add.at(v, inverse, volume)
    np.add.at(b, inverse, buy)
    return unique, v, b
