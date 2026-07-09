"""Where volume traded inside a structure: the developing profile, and the closed ones.

One job: accumulate volume at price from the last confirmed swing to the current
bar, publish its point of control and value area - and, when a swing confirms,
freeze that profile onto the range it described and start a new one.

**The developing range always exists.** It runs from the last confirmed swing to
now. It grows every bar, it never looks ahead, and it survives a break of
structure - unlike a high-low box, which does not exist at all on roughly half of
bars, because ``breaks`` spends a level when price takes it out.

**A closed profile is stamped where it happened.** It keeps the bar span it
covered, so the chart draws it against its own structure rather than against the
right edge. It is known only on the bar that CONFIRMED the swing, never the bar
that made it - the same lag every swing has, and for the same reason.

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

from src.config import profile as store_cfg
from src.config.indicators import profile as cfg
from src.indicators.base import Indicator, Unavailable
from src.profile import store
from src.profile.value_area import EmptyProfile, value_area

logger = logging.getLogger(__name__)

ABOVE, INSIDE, BELOW = "above", "inside", "below"

_NOTHING = {"profile_poc": None, "profile_val": None, "profile_vah": None,
            "profile_from_time": None, "profile_to_time": None,
            "profile_volume": None, "profile_bins": None, "profile_closed": None,
            "value_width": None, "poc_position": None, "poc_distance": None,
            "price_vs_value": None, "delta_at_poc": None}


class Ladder:
    """A running histogram on the tick grid: dense, and sorted by construction.

    Prices land exactly on the 0.25 grid, so a price is an integer index and a
    bar folds in with one vectorised add. A dict of prices would need sorting into
    arrays on every bar, and over a 5,000-bar window that sort dominated
    everything else the chart did.
    """

    SLAB = 512      # grow in slabs; padding by one bar's width reallocates always

    def __init__(self) -> None:
        self._lo: int | None = None            # tick index of self._volume[0]
        self._volume = np.zeros(0, np.int64)
        self._buy = np.zeros(0, np.int64)

    def __bool__(self) -> bool:
        return self._lo is not None

    def add(self, prices, volume, buy) -> None:
        ticks = np.rint(prices / store_cfg.TICK_SIZE).astype(np.int64)
        lo, hi = int(ticks[0]), int(ticks[-1])          # vap prices are ascending
        if self._lo is None:
            self._lo = lo - self.SLAB
            self._volume = np.zeros(hi - lo + 1 + 2 * self.SLAB, np.int64)
            self._buy = np.zeros_like(self._volume)
        else:
            self._grow(lo, hi)
        idx = ticks - self._lo
        # A bar's levels are already unique - the store folds them - so a plain
        # fancy-index add is correct, and np.add.at's unbuffered path is paid for
        # nothing.
        self._volume[idx] += volume
        self._buy[idx] += buy

    def _grow(self, lo: int, hi: int) -> None:
        left = self._lo - lo
        right = hi - (self._lo + len(self._volume) - 1)
        if left <= 0 and right <= 0:
            return
        left = max(left, 0) + (self.SLAB if left > 0 else 0)
        right = max(right, 0) + (self.SLAB if right > 0 else 0)
        self._volume = np.pad(self._volume, (left, right))
        self._buy = np.pad(self._buy, (left, right))
        self._lo -= left

    def arrays(self) -> tuple:
        """Ascending prices and their volumes. Empty levels are dropped."""
        filled = np.flatnonzero(self._volume)
        prices = (self._lo + filled) * store_cfg.TICK_SIZE
        return prices, self._volume[filled], self._buy[filled]


class Profile(Indicator):
    """The developing volume profile, and the finished ones behind it."""

    id = "profile"
    fields = ("profile_poc", "profile_val", "profile_vah",
              "profile_from_time", "profile_to_time", "profile_volume",
              "profile_bins", "profile_closed",
              # The readings. Dimensionless where they can be, so they mean the
              # same thing in a quiet hour and a loud one - the raw levels move
              # with price and with volatility, and these do not.
              "value_width", "poc_position", "poc_distance",
              "price_vs_value", "delta_at_poc")
    depends = ("range_scale", "swing")

    def __init__(self) -> None:
        # A profile is a reading of the present, and only the newest one is drawn
        # - the chart replaces the whole layer each bar. A caller walking WARMUP
        # bars can say so: the histogram keeps accumulating (that state is what
        # the newest reading is made of) while the summary is skipped. Over a
        # 5,000-bar browse window that is 4,999 value areas computed and thrown
        # away, and it made the chart take seconds to draw anything at all.
        #
        # Closing a range is NOT skipped while quiet: it happens once per swing,
        # and those profiles are the ones that stay on the chart.
        self.quiet = False
        self.reset()

    def reset(self) -> None:
        self._first: int | None = None          # first bar time of this range
        self._acc = Ladder()
        self._pending: list = []                # this range's bars, for the split
        self._closed: deque = deque(maxlen=cfg.MAX_CLOSED)

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
        self._observe(ts, prices, volume, buy)

        if up.get("swing"):
            # This bar CONFIRMED a swing that an EARLIER bar made. Everything up
            # to that earlier bar closes the range; the bars after it, including
            # this one, open the next.
            self._close(int(up["swing_time"]), scale)

        return self._publish(scale, ts, event.close)

    # --- state ---------------------------------------------------------------

    def _observe(self, ts: int, prices, volume, buy) -> None:
        if self._first is None:
            self._first = ts
        self._acc.add(prices, volume, buy)
        self._pending.append((ts, prices, volume, buy))

    def _close(self, swing_time: int, scale: float) -> None:
        """Freeze the range that ended at the swing bar; open the next one."""
        inside = [b for b in self._pending if b[0] <= swing_time]
        after = [b for b in self._pending if b[0] > swing_time]

        if inside:
            frozen = Ladder()
            for _, p, v, b in inside:
                frozen.add(p, v, b)
            summary = self._summarise(*frozen.arrays(),
                                      (inside[0][0], inside[-1][0]), scale)
            if summary["profile_poc"] is not None:
                self._closed.append(_as_closed(summary))

        self._acc = Ladder()
        self._pending = []
        self._first = None
        for bar_ts, p, v, b in after:
            self._observe(bar_ts, p, v, b)

    # --- publishing ----------------------------------------------------------

    def _publish(self, scale: float, now: int, close: float) -> dict:
        if self.quiet or not self._acc or self._first is None:
            return dict(_NOTHING)

        row = self._summarise(*self._acc.arrays(), (self._first, now), scale, close)
        row["profile_closed"] = [dict(c) for c in self._closed] if self._closed else None
        return row

    def _summarise(self, prices, volume, buy, span, scale, close=None) -> dict:
        bin_size = scale / cfg.BINS_PER_SCALE
        prices, volume, buy = store.rebin(prices, volume, buy, bin_size)
        try:
            poc, val, vah = value_area(prices, volume)
        except EmptyProfile:
            return dict(_NOTHING)

        row = {
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
            "profile_closed": None,
        }
        row.update(_readings(prices, volume, buy, poc, val, vah, scale, close))
        return row


def _readings(prices, volume, buy, poc, val, vah, scale, close) -> dict:
    """What a profile SAYS, as opposed to where its levels sit.

    Dimensionless wherever it can be. A width in points means one thing at the
    New York open and another at 04:00; the same width in units of a typical bar
    means the same thing at both.
    """
    lo, hi = float(prices[0]), float(prices[-1])

    # How tightly the market agreed on a price. Narrow is balance; wide is a
    # market that kept trading away from itself.
    width = (vah - val) / scale

    # Where value sits inside the range price actually covered, 0 (at the low) to
    # 1 (at the high). Value high while price is low is a different structure
    # from the reverse, and this is the number that says which.
    position = None if hi == lo else (poc - lo) / (hi - lo)

    # Who built the fair price. Every bin carries the volume that crossed the
    # spread to BUY, so the point of control has a sign: a POC made by sellers
    # that price then held is resting demand, at one exact price. Volume at price
    # and aggressor side both live only in the ticks, which is why almost nothing
    # else can compute this.
    at_poc = int(np.flatnonzero(prices == poc)[0])
    poc_volume = int(volume[at_poc])
    delta_at_poc = (2 * int(buy[at_poc]) - poc_volume) / poc_volume if poc_volume else None

    reading = {
        "value_width": width,
        "poc_position": position,
        "delta_at_poc": delta_at_poc,
        "poc_distance": None,
        "price_vs_value": None,
    }
    if close is not None:
        # Price outside the value area is the market declining to accept the
        # price it just built. Inside is acceptance.
        reading["poc_distance"] = (close - poc) / scale
        reading["price_vs_value"] = (ABOVE if close > vah else
                                     BELOW if close < val else INSIDE)
    return reading


def _as_closed(summary: dict) -> dict:
    """A finished profile: what draws it, and what names the range it describes."""
    return {
        "poc": summary["profile_poc"],
        "val": summary["profile_val"],
        "vah": summary["profile_vah"],
        "from_time": summary["profile_from_time"],
        "to_time": summary["profile_to_time"],
        "volume": summary["profile_volume"],
        "bins": summary["profile_bins"],
    }
