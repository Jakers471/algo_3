"""Pin the server-side replay session.

The property that matters most: **seeking to a bar leaves the indicators in the
same state as playing into it**. If that ever breaks, replay silently lies -
a strategy studied at a cut point behaves differently than the same strategy
reached by playing, and nothing in the output says so.

These run against a synthetic packed cache, so they need no real data.
"""

from __future__ import annotations

import json
import queue

import numpy as np
import pytest

from src.chart import packer, store
from src.replay import manager
from src.replay.session import ReplaySession
from src.replay.snapshot import Snapshot

# 5-minute bars starting at a Monday 18:05 ET (globex reopen) = 23:05 UTC.
FIRST = 1_719_270_300  # 2024-06-24 23:05:00 UTC
STEP = 300
N = 600               # 50 hours - crosses several session boundaries


@pytest.fixture
def packed(tmp_path, monkeypatch):
    monkeypatch.setattr("src.config.chart.CACHE_DIR", tmp_path)
    store._BARS.clear(); store._TIMES.clear(); store._META.clear()

    recs = np.empty(N, dtype=packer.BAR_DTYPE)
    recs["time"] = np.arange(FIRST, FIRST + N * STEP, STEP, dtype="<u4")
    base = 5000.0 + np.arange(N) * 0.25
    recs["open"] = base
    recs["high"] = base + 1.0
    recs["low"] = base - 1.0
    recs["close"] = base + 0.5
    recs["volume"] = 10.0
    for field in packer.ORDER_FLOW_FIELDS:
        recs[field] = np.float32("nan")     # a bar file, like NQ: no order flow

    bars_fp, times_fp, meta_fp = packer.paths_for("TT", "5m")
    recs.tofile(bars_fp)
    recs["time"].astype(packer.TIME_DTYPE).tofile(times_fp)
    meta_fp.write_text(json.dumps({
        "format_version": packer.FORMAT_VERSION, "symbol": "TT", "timeframe": "5m",
        "count": N, "bar_bytes": packer.BAR_DTYPE.itemsize, "order_flow": False,
        "first_time": int(recs["time"][0]), "last_time": int(recs["time"][-1]),
    }))
    yield recs
    manager.stop_all()


def test_seed_warms_indicators_without_publishing(packed):
    s = ReplaySession("TT", "5m")
    q = s.subscribe()
    info = s.seed(200, history=100)

    assert info["first_index"] == 100
    assert info["cursor"] == 199
    assert q.empty(), "the warmup must not publish - it is not a replay step"
    # The columns are whatever the registry publishes, in dependency order.
    assert info["fields"] == ["session", "session_new",
                             "delta", "buy_volume", "sell_volume", "trades",
                             "absorption", "absorption_side"]


def test_seeking_equals_playing_into_the_same_bar(packed):
    """The property the whole design rests on."""
    seek = ReplaySession("TT", "5m")
    seek.seed(400, history=200)

    played = ReplaySession("TT", "5m")
    played.seed(300, history=100)
    for _ in range(100):
        played.step()

    assert seek.cursor == played.cursor == 399

    a, b = seek.step(), played.step()
    assert a.time == b.time
    assert a.bar == b.bar
    assert a.fields == b.fields          # identical indicator state
    assert a.marks == b.marks


def test_a_bar_without_order_flow_publishes_None_never_zero(packed):
    """This fixture is a bar file: no aggressor was ever recorded.

    Zero would claim buying and selling were balanced. None says nobody wrote it
    down. A backtest would believe the first.
    """
    s = ReplaySession("TT", "5m")
    s.seed(100, history=50)
    row = s.step().fields
    assert row["delta"] is None
    assert row["buy_volume"] is None and row["sell_volume"] is None
    assert row["trades"] is None
    # And absorption, which depends on delta, refuses in turn rather than
    # deciding that a bar with no recorded aggressor absorbed nothing.
    assert row["absorption"] is None and row["absorption_side"] is None


def test_the_snapshot_bar_carries_delta_as_null_when_absent(packed):
    s = ReplaySession("TT", "5m")
    s.seed(100, history=50)
    bar = s.step().to_dict()["bar"]
    assert bar["delta"] is None, "NaN is not valid JSON and would not mean absent"
    json.dumps(bar)   # must survive the wire


def test_step_publishes_to_every_subscriber(packed):
    """The chart and the TUI must see the same row - that is the point."""
    s = ReplaySession("TT", "5m")
    s.seed(100, history=50)
    chart, tui = s.subscribe(), s.subscribe()

    snap = s.step()
    assert chart.get_nowait().to_dict() == tui.get_nowait().to_dict() == snap.to_dict()


def test_marks_never_precede_their_bar(packed):
    s = ReplaySession("TT", "5m")
    s.seed(50, history=50)
    seen = 0
    for _ in range(400):
        snap = s.step()
        if snap is None:
            break
        for mark in snap.marks:
            assert mark["time"] <= snap.time
            seen += 1
    assert seen > 0, "this window should cross at least one session boundary"


def test_seq_is_monotonic_and_resets_on_seed(packed):
    s = ReplaySession("TT", "5m")
    s.seed(100, history=50)
    seqs = [s.step().seq for _ in range(5)]
    assert seqs == [1, 2, 3, 4, 5]

    s.seed(200, history=50)
    assert s.step().seq == 1


def test_step_stops_at_the_end_of_the_data(packed):
    s = ReplaySession("TT", "5m")
    s.seed(N - 1, history=10)   # cursor sits on the second-to-last bar
    assert s.cursor == N - 2
    assert s.step() is not None  # reveals the last bar
    assert s.cursor == N - 1 and s.at_end
    assert s.step() is None      # and there is nothing after it


def test_cursor_never_passes_the_last_bar(packed):
    s = ReplaySession("TT", "5m")
    s.seed(N, history=10)
    assert s.cursor == N - 1
    assert s.at_end and s.step() is None


def test_slow_subscriber_drops_its_own_rows_not_everyone_s(packed, monkeypatch):
    """A stalled TUI must not stall the chart, so the queue drops its oldest."""
    monkeypatch.setattr("src.config.replay.SUBSCRIBER_QUEUE_MAX", 4)
    s = ReplaySession("TT", "5m")
    s.seed(100, history=50)
    slow = s.subscribe()

    for _ in range(10):
        s.step()

    assert slow.qsize() == 4                       # bounded, not blocked
    newest = [slow.get_nowait().seq for _ in range(4)]
    assert newest == [7, 8, 9, 10]                 # oldest dropped, newest kept


def test_transport_changes_are_published_to_subscribers(packed):
    """The Play button repaints from the server, so the TUI cannot disagree."""
    s = ReplaySession("TT", "5m")
    s.seed(100, history=50)
    q = s.subscribe()

    s.play()
    assert q.get(timeout=1)["state"]["playing"] is True
    s.pause()
    assert q.get(timeout=1)["state"]["playing"] is False


def test_speed_change_is_published(packed):
    s = ReplaySession("TT", "5m")
    s.seed(100, history=50)
    q = s.subscribe()
    s.set_speed(2)
    assert q.get(timeout=1)["state"]["speed"] == 2


def test_bad_speed_is_rejected(packed):
    s = ReplaySession("TT", "5m")
    with pytest.raises(ValueError):
        s.set_speed(3)


def test_speed_sets_the_interval(packed):
    s = ReplaySession("TT", "5m")
    s.set_speed(4)
    assert s.interval == pytest.approx(0.125)      # 500ms base / 4


def test_starting_a_replay_retires_the_ones_that_owner_left_behind(packed):
    """A refreshed browser forgets its session id but not its own id.

    Without this, each refresh strands a session until the idle reaper notices,
    and a table attaching in the meantime cannot tell which replay is "the" one.
    """
    first = manager.create("TT", "5m", owner="chart-abc")
    second = manager.create("TT", "5m", owner="chart-abc")
    other = manager.create("TT", "5m", owner="chart-xyz")
    assert manager.count() == 3

    retired = manager.stop_owned_by("chart-abc")
    assert retired == 2
    assert manager.count() == 1
    assert manager.get(other.id) is other
    for session in (first, second):
        with pytest.raises(KeyError):
            manager.get(session.id)


def test_an_empty_owner_retires_nothing(packed):
    """An anonymous caller must not be able to kill every anonymous session."""
    manager.create("TT", "5m")
    manager.create("TT", "5m")
    assert manager.stop_owned_by("") == 0
    assert manager.count() == 2


def test_sessions_report_their_owner_and_start_time(packed):
    manager.create("TT", "5m", owner="chart-abc")
    info = manager.list_sessions()[0]
    assert info["owner"] == "chart-abc"
    assert info["started"] > 0


def test_manager_retires_a_session(packed):
    s = manager.create("TT", "5m")
    assert manager.get(s.id) is s
    manager.stop(s.id)
    with pytest.raises(KeyError):
        manager.get(s.id)


def test_stop_closes_open_streams(packed):
    s = manager.create("TT", "5m")
    s.seed(100, history=50)
    q = s.subscribe()
    s.stop()
    assert q.get_nowait() is None                  # sentinel ends the SSE loop


def test_snapshot_serializes_flat(packed):
    s = ReplaySession("TT", "5m")
    s.seed(100, history=50)
    d = s.step().to_dict()
    assert set(d) == {"seq", "index", "total", "time", "bar", "fields", "marks", "at_end"}
    assert isinstance(d["fields"], dict) and "session" in d["fields"]
    json.dumps(d)   # must survive the wire
