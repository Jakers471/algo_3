"""A replay in progress: the cursor, the indicator state, and who is watching.

One job: own the position in the data and the live indicator state, advance them
one bar at a time, and publish a Snapshot to every subscriber.

This is the piece that makes the chart and the TUI agree. Neither of them steps
anything; both subscribe to the same stream of rows. There is one cursor, one
indicator state, one computation - so two views of it cannot disagree, and a
third view costs nothing to add.

Why the state lives here rather than in the browser: an indicator is a state
machine, and state machines cannot be resumed from the middle. When the cursor
sat in the client, every overlay refresh had to re-run the indicators over the
whole visible buffer just to rediscover which session we were in - 45ms, every
few bars. Here the state is simply *there*, and a step costs one update() call.

Seeking backwards is the same idea in reverse: ``seed`` replays the warmup bars
silently, without publishing, so the indicators arrive at the cut point holding
exactly what they would have held had you played into it. No lookahead is
possible because no bar past the cursor is ever fed to anything.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
import uuid

from src.chart import overlays, store
from src.config import chart as chart_cfg
from src.config import replay as replay_cfg
from src.replay.snapshot import Snapshot

logger = logging.getLogger(__name__)


class ReplaySession:
    """One cursor over one symbol/timeframe, with live indicator state."""

    def __init__(self, symbol: str, timeframe: str, owner: str = "",
                 profile_mode: str | None = None) -> None:
        self.id = uuid.uuid4().hex[:12]
        self.symbol = symbol
        self.timeframe = timeframe
        # Which volume-profile range this session draws. Changing it needs a new
        # session: the indicator's state IS the range it has accumulated, and a
        # state machine cannot be re-pointed halfway through.
        self.profile_mode = profile_mode
        # Who asked for this replay. A browser identifies itself with a stable
        # id, so starting a new replay retires the one it left behind - even
        # across a page refresh, when it has forgotten the session id itself.
        self.owner = owner
        self.started = time.time()

        self.registry = overlays.build_registry(profile_mode)
        self.total = store.count(symbol, timeframe)

        self.cursor = -1          # dataset index of the last bar revealed
        self.first_index = 0      # start of the warmed-up window
        self.seq = 0
        self.speed = 1
        self.playing = False

        self.last_seen = time.monotonic()

        self._subscribers: list[queue.Queue] = []
        self._lock = threading.RLock()
        self._play_thread: threading.Thread | None = None
        self._stop_play = threading.Event()

    # --- lifecycle ----------------------------------------------------------

    def seed(self, index: int, history: int | None = None) -> dict:
        """Cut to ``index``: replay the warmup silently, publish nothing.

        Returns what a fresh subscriber needs to draw the history: the window
        bounds and the marks the warmup produced.
        """
        history = history or chart_cfg.HISTORY_BARS
        with self._lock:
            self.pause()
            index = max(0, min(int(index), self.total))
            self.first_index = max(0, index - history)
            self.registry.reset()
            self.seq = 0

            bars = store.slice_bars(self.symbol, self.timeframe, self.first_index,
                                    index - self.first_index)
            marks: list[dict] = []
            events = overlays.bar_events(bars, self.symbol, self.timeframe)
            for i, (bar, event) in enumerate(zip(bars, events)):
                row = self.registry.update(event)
                marks.extend(overlays.marks_for(int(bar["time"]), row, is_first=(i == 0),
                                                close=float(bar["close"])))

            self.cursor = index - 1
            logger.info("Replay %s: seeded at %d (warmed %d bars)", self.id, index, len(bars))
            return {
                "session": self.id,
                "symbol": self.symbol,
                "timeframe": self.timeframe,
                "first_index": self.first_index,
                "cursor": self.cursor,
                "total": self.total,
                "overlays": overlays.group_marks(marks),
                "fields": self.registry.field_names(),
                "groups": self.registry.field_groups(),
            }

    @property
    def at_end(self) -> bool:
        return self.cursor >= self.total - 1

    # --- stepping -----------------------------------------------------------

    def step(self) -> Snapshot | None:
        """Reveal the next bar. Returns the snapshot, or None at the end."""
        with self._lock:
            if self.at_end:
                return None

            index = self.cursor + 1
            bars = store.slice_bars(self.symbol, self.timeframe, index, 1)
            if len(bars) == 0:
                return None

            bar = bars[0]
            event = overlays.bar_events(bars, self.symbol, self.timeframe)[0]
            row = self.registry.update(event)

            self.cursor = index
            self.seq += 1
            snapshot = Snapshot(
                seq=self.seq,
                index=index,
                total=self.total,
                time=int(bar["time"]),
                bar={
                    "open": float(bar["open"]), "high": float(bar["high"]),
                    "low": float(bar["low"]), "close": float(bar["close"]),
                    "volume": float(bar["volume"]),
                    # NaN is not valid JSON and would not mean "absent" to a
                    # browser anyway. None crosses the wire as null.
                    "delta": overlays._optional(float(bar["delta"])),
                },
                fields=row,
                marks=overlays.marks_for(int(bar["time"]), row, close=float(bar["close"])),
                at_end=self.at_end,
            )

        self._publish(snapshot)
        return snapshot

    # --- playback -----------------------------------------------------------

    def set_speed(self, speed: int) -> None:
        if speed not in replay_cfg.SPEEDS:
            raise ValueError(f"speed must be one of {replay_cfg.SPEEDS}")
        self.speed = speed
        self._publish_state()

    @property
    def interval(self) -> float:
        return (chart_cfg.BASE_STEP_MS / self.speed) / 1000.0

    def play(self) -> None:
        """Advance on a timer until paused or out of data."""
        with self._lock:
            if self.playing or self.at_end:
                return
            self.playing = True
            self._stop_play.clear()
            self._play_thread = threading.Thread(
                target=self._run, name=f"replay-{self.id}", daemon=True)
            self._play_thread.start()
        # Subscribers learn the transport state from us, never from their own
        # button press - otherwise a second view (the TUI) would never know.
        self._publish_state()

    def _run(self) -> None:
        # Sleep on the stop event, not on time: a pause takes effect immediately
        # rather than after the current bar's interval has elapsed.
        while not self._stop_play.wait(self.interval):
            if self.step() is None:
                break
        self.playing = False
        self._publish_state()

    def pause(self) -> None:
        was_playing = self.playing
        self._stop_play.set()
        self.playing = False
        if was_playing:
            self._publish_state()

    def stop(self) -> None:
        self.pause()
        for q in list(self._subscribers):
            self._offer(q, None)   # sentinel: close the stream

    # --- fan-out ------------------------------------------------------------

    def subscribe(self) -> queue.Queue:
        """A queue of snapshots. The chart takes one; the TUI takes another."""
        q: queue.Queue = queue.Queue(maxsize=replay_cfg.SUBSCRIBER_QUEUE_MAX)
        with self._lock:
            self._subscribers.append(q)
        self.last_seen = time.monotonic()
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        with self._lock:
            if q in self._subscribers:
                self._subscribers.remove(q)
        self.last_seen = time.monotonic()

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    def _publish(self, snapshot: Snapshot) -> None:
        for q in list(self._subscribers):
            self._offer(q, snapshot)

    def _publish_state(self) -> None:
        """Tell subscribers the transport changed (paused, hit the end)."""
        for q in list(self._subscribers):
            self._offer(q, {"state": {"playing": self.playing, "speed": self.speed,
                                      "at_end": self.at_end, "cursor": self.cursor}})

    @staticmethod
    def _offer(q: queue.Queue, item) -> None:
        """Never block. A slow subscriber loses its oldest row, not everyone's."""
        try:
            q.put_nowait(item)
        except queue.Full:
            try:
                q.get_nowait()
                q.put_nowait(item)
            except queue.Empty:
                pass
