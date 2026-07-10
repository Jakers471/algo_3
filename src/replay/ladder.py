"""The rungs above the replay's own timeframe: same indicators, coarser bars.

One job: fold the base bars a session reveals into a coarser bar, and when that
coarser bar CLOSES, run a registry of its own over it and hand back a snapshot.

Why this exists. The indicators are scale-free - a swing is `RETRACE x
range_scale` of a pullback, and `range_scale` is measured from the bars in front
of it - so the same code says something different, and equally true, at 30s, 3m
and 15m. Watching all three at once is watching one market at three scales.

Why it is not three replays. Three sessions would have three cursors, three
clocks and three warmups, and nothing would keep them on the same bar; they
would drift the moment one paused. A rung here is fed by the base cursor, so a
15m bar closes exactly when the thirtieth 30s bar closes, by construction. There
is one clock, and alignment is a property of the arithmetic rather than of any
coordination.

Nothing here can see the future: a rung is fed the bar the cursor just revealed
and never a bar beyond it, and it emits only on a bar that has closed. A rung
whose bar is still forming publishes nothing at all - it does not publish a
half-formed bar's readings, because a bar that is not closed has no close.

The aggregation is the one the bar store itself uses: first open, max high, min
low, last close, summed volume - and summed order flow, but only when EVERY base
bar carried it. One missing delta makes the rung's delta absent, never a partial
sum of the bars that happened to have one.
"""

from __future__ import annotations

import logging

import pandas as pd

from src.chart import overlays
from src.config.indicators import profile as profile_cfg
from src.events.types import BarClose
from src.profile import store as vap_store
from src.replay.snapshot import Snapshot

logger = logging.getLogger(__name__)


def rungs_above(timeframe: str, ladder: tuple) -> list[str]:
    """The ladder's timeframes that a base bar can be folded into, exactly.

    A rung must be a whole multiple of the base: 30s folds into 3m (six of them)
    and into 15m (thirty), but 45s folds into neither, and a rung built from a
    fraction of a bar would be inventing the fraction. Anything that does not
    divide is left off the ladder rather than approximated.
    """
    base = overlays.step_seconds(timeframe)
    out = []
    for rung in ladder:
        step = overlays.step_seconds(rung)
        if step > base and step % base == 0:
            out.append(rung)
    return out


class Rung:
    """One coarser timeframe: an accumulating bar, and a registry over it."""

    def __init__(self, timeframe: str, symbol: str, profile_mode: str | None = None) -> None:
        self.timeframe = timeframe
        self.symbol = symbol
        self.seconds = overlays.step_seconds(timeframe)
        self.registry = overlays.build_registry(profile_mode)
        self.seq = 0
        self._pending: dict | None = None
        self._bucket: int | None = None

    def reset(self) -> None:
        self.registry.reset()
        self.seq = 0
        self._pending = None
        self._bucket = None

    def feed(self, event: BarClose, *, index: int, total: int,
             quiet: bool = False) -> Snapshot | None:
        """Fold one base bar in. Returns a snapshot only when a rung bar closes.

        ``quiet`` warms the registry without paying for marks - the same trick
        ``seed`` uses on the base rung, for the same reason: a silent replay of
        the warmup must arrive at the cut point holding the state it would have
        held, and nothing that happened during it is drawn.
        """
        epoch = int(event.ts.timestamp())
        # Which coarse bar this base bar belongs to. Bars are close-stamped, so a
        # bar at exactly the boundary is the LAST bar of the rung it closes, not
        # the first of the next: `(t - step, t]`. Hence the ceiling on t - 1.
        bucket = (epoch - 1) // self.seconds + 1

        if self._bucket is not None and bucket != self._bucket:
            # A gap in the tape can skip a boundary entirely. The pending bar is
            # still a closed bar - it just holds fewer base bars than a full one
            # would - so close it on the price it last traded at, not on this
            # bar's, which belongs to a later rung.
            closed = self._close(index, total, quiet=quiet)
            self._start(bucket, event)
            return closed

        if self._bucket is None:
            self._start(bucket, event)
        else:
            self._extend(event)

        if epoch == self._bucket * self.seconds:
            return self._close(index, total, quiet=quiet)
        return None

    # --- the fold -----------------------------------------------------------

    def _start(self, bucket: int, event: BarClose) -> None:
        self._bucket = bucket
        self._pending = {
            "open": event.open, "high": event.high, "low": event.low,
            "close": event.close, "volume": event.volume,
            "delta": event.delta, "buy_volume": event.buy_volume,
            "sell_volume": event.sell_volume, "trades": event.trades,
        }

    def _extend(self, event: BarClose) -> None:
        bar = self._pending
        bar["high"] = max(bar["high"], event.high)
        bar["low"] = min(bar["low"], event.low)
        bar["close"] = event.close
        bar["volume"] += event.volume
        for name in ("delta", "buy_volume", "sell_volume", "trades"):
            # None means the bar never carried it. A sum that skips the missing
            # ones would claim a total the data cannot support.
            value = getattr(event, name)
            if bar[name] is None or value is None:
                bar[name] = None
            else:
                bar[name] += value

    def _close(self, index: int, total: int, *, quiet: bool) -> Snapshot | None:
        bar = self._pending
        epoch = self._bucket * self.seconds
        self._pending = None
        self._bucket = None
        if bar is None:
            return None

        event = BarClose(
            ts=pd.Timestamp(epoch, unit="s", tz="UTC"),
            open=bar["open"], high=bar["high"], low=bar["low"], close=bar["close"],
            volume=bar["volume"], delta=bar["delta"], buy_volume=bar["buy_volume"],
            sell_volume=bar["sell_volume"], trades=bar["trades"],
            vap=self._vap(epoch),
        )

        profile = self.registry.get("profile")
        if profile is not None:
            profile.quiet = quiet
        row = self.registry.update(event)
        if profile is not None:
            profile.quiet = False

        if quiet:
            return None       # warmup: the state is what we came for, not the row

        self.seq += 1
        return Snapshot(
            seq=self.seq,
            # The BASE cursor's position. A rung has no index of its own in any
            # store, and inventing one would let a reader think it could seek to
            # it. What it can honestly say is which base bar closed it.
            index=index,
            total=total,
            time=epoch,
            bar={"open": bar["open"], "high": bar["high"], "low": bar["low"],
                 "close": bar["close"], "volume": bar["volume"],
                 "delta": overlays._optional(bar["delta"])},
            fields=row,
            marks=overlays.marks_for(epoch, row, close=bar["close"]),
            at_end=False,
            rung=self.timeframe,
        )

    def _vap(self, epoch: int) -> tuple | None:
        """Volume at price over the rung's whole span, straight from the ticks.

        Not a fold of the base bars' histograms - it is the same store, sliced
        wider. A bar file has no volume at price at all, and this returns None
        rather than spreading volume across a range it never observed.
        """
        if not (profile_cfg.ENABLED and self.registry.has("profile")):
            return None
        try:
            return vap_store.histogram(self.symbol, profile_cfg.BASE_TIMEFRAME,
                                       epoch - self.seconds, epoch)
        except vap_store.NotBuilt:
            return None


class Ladder:
    """Every rung above a session's base timeframe. Fed one base bar at a time."""

    def __init__(self, symbol: str, timeframe: str, ladder: tuple,
                 profile_mode: str | None = None) -> None:
        self.rungs = [Rung(name, symbol, profile_mode)
                      for name in rungs_above(timeframe, ladder)]
        if self.rungs:
            logger.info("Ladder above %s: %s", timeframe,
                        ", ".join(r.timeframe for r in self.rungs))

    @property
    def timeframes(self) -> list[str]:
        return [rung.timeframe for rung in self.rungs]

    def reset(self) -> None:
        for rung in self.rungs:
            rung.reset()

    def feed(self, event: BarClose, *, index: int, total: int,
             quiet: bool = False) -> list[Snapshot]:
        """One base bar in; a snapshot out for each rung that just closed a bar."""
        out = []
        for rung in self.rungs:
            snapshot = rung.feed(event, index=index, total=total, quiet=quiet)
            if snapshot is not None:
                out.append(snapshot)
        return out
