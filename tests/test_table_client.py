"""Pin the table's stream client against the reconnect storm it caused.

Switching timeframe on the chart retires the replay session. The table was
watching it, and three things went wrong at once:

  1. `stream()` is a generator, so the server sent `200 OK` before `manager.get`
     ever ran. The dead session surfaced as a KeyError on the first frame - long
     after the promise of a 200 - and the handler thread raised.
  2. The client therefore saw a *clean* connection close, indistinguishable from
     a healthy one, and retried with no delay: 200 reconnects in 3 seconds.
  3. Nothing looked for the session that replaced it.

All three are pinned here.
"""

from __future__ import annotations

import queue
import urllib.error

import pytest

from src.replay import manager, routes
from src.table import client


@pytest.fixture(autouse=True)
def no_sessions():
    manager.stop_all()
    yield
    manager.stop_all()


# --- the server side --------------------------------------------------------

def test_streaming_a_dead_session_yields_nothing_instead_of_raising():
    """The generator must not raise into the handler thread after headers went out."""
    frames = list(routes.stream("deadbeef"))
    assert frames == []


def test_sessions_route_lists_nothing_when_no_replay_runs():
    status, _, body, _ = routes.handle_get("/api/replay/sessions", {})
    assert status == 200
    import json
    assert json.loads(body) == {"sessions": []}


# --- the client side --------------------------------------------------------

@pytest.fixture
def patched(monkeypatch):
    def fake_list(base_url):
        return fake_list.sessions
    fake_list.sessions = []
    monkeypatch.setattr(client, "list_sessions", fake_list)
    return fake_list


def test_backoff_grows_and_never_retries_immediately(monkeypatch):
    """A zero-delay retry against a dead session is the storm. Never do it."""
    from src.config import table as cfg

    stream = client.SnapshotStream("http://test", "s1")
    waits = []
    monkeypatch.setattr(stream._stop, "wait", lambda d: waits.append(d) or False)

    stream._backoff()
    stream._backoff()
    stream._backoff()

    assert waits[0] == cfg.RECONNECT_DELAY_S
    assert waits[1] == cfg.RECONNECT_DELAY_S * 2
    assert waits[2] == cfg.RECONNECT_DELAY_S * 4
    assert all(w > 0 for w in waits)


def test_backoff_is_capped(monkeypatch):
    from src.config import table as cfg

    stream = client.SnapshotStream("http://test", "s1")
    monkeypatch.setattr(stream._stop, "wait", lambda _d: False)
    for _ in range(20):
        stream._backoff()
    assert stream._delay == cfg.RECONNECT_DELAY_MAX_S


def test_alive_is_true_while_the_session_is_listed(patched):
    patched.sessions = [{"id": "s1"}]
    stream = client.SnapshotStream("http://test", "s1")
    assert stream._alive() is True

    patched.sessions = []
    assert stream._alive() is False


def test_a_server_we_cannot_reach_is_not_a_retired_session(monkeypatch):
    """Do not adopt, and do not give up, because the network hiccuped."""
    def boom(_url):
        raise OSError("connection refused")
    monkeypatch.setattr(client, "list_sessions", boom)

    stream = client.SnapshotStream("http://test", "s1")
    assert stream._alive() is True


def test_adopting_the_replacement_session(patched):
    """Switching timeframe retires one session and starts another. Follow it."""
    patched.sessions = [{"id": "s2", "symbol": "NQT", "timeframe": "5m", "fields": ["session"]}]
    stream = client.SnapshotStream("http://test", "s1")

    assert stream._adopt() is True
    assert stream.session_id == "s2"

    payload = stream.queue.get_nowait()
    assert payload["session_changed"]["id"] == "s2"
    assert payload["session_changed"]["timeframe"] == "5m"


def test_adopting_resets_the_backoff(patched, monkeypatch):
    from src.config import table as cfg

    patched.sessions = [{"id": "s2", "symbol": "NQT", "timeframe": "5m"}]
    stream = client.SnapshotStream("http://test", "s1")
    monkeypatch.setattr(stream._stop, "wait", lambda _d: False)
    stream._backoff(); stream._backoff()
    assert stream._delay > cfg.RECONNECT_DELAY_S

    stream._adopt()
    assert stream._delay == cfg.RECONNECT_DELAY_S


def test_never_adopt_when_the_choice_is_ambiguous(patched):
    """Two replays running: guessing which one the user meant would be worse."""
    patched.sessions = [{"id": "a"}, {"id": "b"}]
    stream = client.SnapshotStream("http://test", "s1")
    assert stream._adopt() is False
    assert stream.session_id == "s1"


def test_never_adopt_when_nothing_is_running(patched):
    patched.sessions = []
    stream = client.SnapshotStream("http://test", "s1")
    assert stream._adopt() is False
    assert stream.queue.empty()


def test_adoption_can_be_turned_off(patched, monkeypatch):
    monkeypatch.setattr("src.config.table.ADOPT_NEW_SESSION", False)
    patched.sessions = [{"id": "s2", "symbol": "NQT", "timeframe": "5m"}]
    stream = client.SnapshotStream("http://test", "s1")
    assert stream._adopt() is False


def test_adopting_a_session_without_our_rung_falls_back_to_its_base():
    """A silent table is the worst failure: it looks like a working one.

    The chart switches from a 30s replay to a 15m one. A 15m replay cannot
    publish a 30s row - a rung is folded UP, and the bars to fold do not exist -
    so a table still filtering for 30s would sit empty forever, saying nothing.
    """
    from src.table.client import SnapshotStream

    stream = SnapshotStream("http://x", "old", rung="30s")
    effective = stream._rung_of({"id": "new", "symbol": "NQ", "timeframe": "15m",
                                 "rungs": ["15m"]})
    assert effective == "15m"
    assert stream.rung == "15m", "the filter must follow, or nothing is delivered"


def test_adopting_a_session_that_does_have_our_rung_keeps_it():
    from src.table.client import SnapshotStream

    stream = SnapshotStream("http://x", "old", rung="15m")
    effective = stream._rung_of({"id": "new", "symbol": "NQT", "timeframe": "30s",
                                 "rungs": ["30s", "3m", "15m"]})
    assert effective == "15m" and stream.rung == "15m"


def test_a_stream_with_no_rung_reads_every_row():
    """The default table watches the base rung by name, never by silence."""
    from src.table.client import SnapshotStream

    stream = SnapshotStream("http://x", "s")
    assert stream.rung is None
    assert stream._rung_of({"timeframe": "5m", "rungs": ["5m", "15m"]}) == "5m"
