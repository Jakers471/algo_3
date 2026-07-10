"""Pin the ladder: the coarser scales a replay publishes alongside its own.

Two properties carry the whole feature.

**A rung's bar is the bar the store would have built.** If the fold drifts from
pandas' own resample, then the 15m table is describing a market that does not
exist, and it will disagree with a 15m chart for reasons no one can find.

**Seeking equals playing, per rung.** The base session already guarantees this;
a rung that warmed differently would silently hold different indicator state at a
cut point - the exact failure the server-side replay was built to prevent.

Synthetic bars, so no real data is needed.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from src.chart import packer, store
from src.events.types import BarClose
from src.replay import manager
from src.replay.ladder import Ladder, Rung, rungs_above
from src.replay.session import ReplaySession

FIRST = 1_719_270_300      # 2024-06-24 23:05:00 UTC
STEP = 30
N = 2_000                  # 16.7 hours of 30s bars


@pytest.fixture
def packed(tmp_path, monkeypatch):
    monkeypatch.setattr("src.config.chart.CACHE_DIR", tmp_path)
    store._BARS.clear(); store._TIMES.clear(); store._META.clear()

    # Start on a 15m boundary so the rungs close cleanly, as real bars do.
    first = FIRST - (FIRST % 900) + STEP
    recs = np.empty(N, dtype=packer.BAR_DTYPE)
    recs["time"] = np.arange(first, first + N * STEP, STEP, dtype="<u4")
    walk = np.cumsum(np.sin(np.arange(N) / 7.0)) * 2.0
    recs["open"] = 5000.0 + walk
    recs["high"] = recs["open"] + 1.5
    recs["low"] = recs["open"] - 1.5
    recs["close"] = recs["open"] + 0.5
    recs["volume"] = 10.0
    for field in packer.ORDER_FLOW_FIELDS:
        recs[field] = np.float32("nan")

    bars_fp, times_fp, meta_fp = packer.paths_for("TT", "30s")
    recs.tofile(bars_fp)
    recs["time"].astype(packer.TIME_DTYPE).tofile(times_fp)
    meta_fp.write_text(json.dumps({
        "format_version": packer.FORMAT_VERSION, "symbol": "TT", "timeframe": "30s",
        "count": N, "bar_bytes": packer.BAR_DTYPE.itemsize, "order_flow": False,
        "first_time": int(recs["time"][0]), "last_time": int(recs["time"][-1]),
    }))
    yield recs
    manager.stop_all()


def events(recs):
    times = pd.to_datetime(recs["time"].astype("int64"), unit="s", utc=True)
    return [BarClose(ts=t, open=float(r["open"]), high=float(r["high"]),
                     low=float(r["low"]), close=float(r["close"]),
                     volume=float(r["volume"]))
            for t, r in zip(times, recs)]


def test_a_rung_must_divide_the_base_exactly():
    """A rung built from a fraction of a bar would be inventing the fraction."""
    assert rungs_above("30s", ("30s", "3m", "15m")) == ["3m", "15m"]
    assert rungs_above("3m", ("30s", "3m", "15m")) == ["15m"]
    assert rungs_above("15m", ("30s", "3m", "15m")) == []      # nothing above it
    assert rungs_above("2m", ("30s", "3m", "15m")) == []       # 3m/2m is not whole


def test_the_fold_is_the_bar_the_store_would_have_built(packed):
    """The ladder's 15m bar and pandas' 15m bar are the same bar."""
    rung = Rung("15m", "TT")
    folded = []
    for i, event in enumerate(events(packed)):
        snapshot = rung.feed(event, index=i, total=len(packed))
        if snapshot is not None:
            folded.append({"time": snapshot.time, **snapshot.bar})

    frame = pd.DataFrame({
        "open": packed["open"], "high": packed["high"], "low": packed["low"],
        "close": packed["close"], "volume": packed["volume"],
    }, index=pd.to_datetime(packed["time"].astype("int64"), unit="s", utc=True))
    grouped = frame.resample("900s", closed="right", label="right")
    truth = grouped.agg({"open": "first", "high": "max", "low": "min",
                         "close": "last", "volume": "sum"}).dropna()
    # pandas closes the final bucket whether or not its 30 bars arrived. The
    # ladder does not: a bar that has not closed has no close, and publishing a
    # partial one would have the 15m table reading a bar the store never built.
    complete = grouped.size() == 900 // STEP
    truth = truth[complete.reindex(truth.index, fill_value=False)]

    assert len(folded) == len(truth), "one rung bar per COMPLETE 15m bucket"
    for got, (ts, want) in zip(folded, truth.iterrows()):
        assert got["time"] == int(ts.timestamp())
        for name in ("open", "high", "low", "close", "volume"):
            assert got[name] == pytest.approx(float(want[name])), name


def test_a_rung_bar_closes_on_the_base_bar_that_completes_it(packed):
    """Alignment is arithmetic, not coordination: same tick, both rows."""
    ladder = Ladder("TT", "30s", ("30s", "3m", "15m"))
    for i, event in enumerate(events(packed)):
        epoch = int(event.ts.timestamp())
        emitted = {s.rung: s for s in ladder.feed(event, index=i, total=len(packed))}
        assert ("15m" in emitted) == (epoch % 900 == 0)
        assert ("3m" in emitted) == (epoch % 180 == 0)
        for rung, snapshot in emitted.items():
            # A rung's row is stamped at ITS bar's close - the same instant as
            # the base bar that completed it, never a bar late.
            assert snapshot.time == epoch
            assert snapshot.index == i


def test_a_forming_rung_bar_publishes_nothing(packed):
    """A bar that has not closed has no close. It says nothing at all."""
    rung = Rung("15m", "TT")
    rows = [rung.feed(e, index=i, total=N) for i, e in enumerate(events(packed)[:29])]
    assert rows == [None] * 29, "29 of the 30 base bars leave the 15m bar forming"


def test_order_flow_absent_on_one_base_bar_is_absent_on_the_rung():
    """A partial sum would claim a total the data cannot support."""
    rung = Rung("3m", "TT")
    start = 1_719_273_600     # a 3m boundary
    snapshot = None
    for i in range(6):
        ts = pd.Timestamp(start + (i + 1) * 30, unit="s", tz="UTC")
        # The third bar never recorded an aggressor; the other five did.
        delta = None if i == 2 else 5.0
        snapshot = rung.feed(
            BarClose(ts=ts, open=1.0, high=2.0, low=0.5, close=1.5, volume=10.0,
                     delta=delta, buy_volume=delta, sell_volume=delta, trades=delta),
            index=i, total=6) or snapshot

    assert snapshot is not None and snapshot.rung == "3m"
    assert snapshot.bar["delta"] is None, "one missing delta makes the rung's absent"
    assert snapshot.bar["volume"] == pytest.approx(60.0), "volume was never missing"


def test_seeking_a_rung_equals_playing_into_it(packed):
    """The property the whole replay rests on, now once per scale."""
    seek = ReplaySession("TT", "30s")
    seek.seed(1_200, history=600)

    played = ReplaySession("TT", "30s")
    played.seed(900, history=300)
    for _ in range(300):
        played.step()

    assert seek.cursor == played.cursor == 1_199

    a, b = seek.subscribe(), played.subscribe()
    for _ in range(60):        # two full 15m bars past the cut
        seek.step()
        played.step()

    # `seq` counts rows published since the seed, so it differs by construction:
    # one session published 300 rows getting here and the other published none.
    # Everything the row SAYS about the market must be identical.
    rows_a = [drop_seq(s.to_dict()) for s in drain(a)]
    rows_b = [drop_seq(s.to_dict()) for s in drain(b)]
    assert [r["rung"] for r in rows_a] == [r["rung"] for r in rows_b]
    assert rows_a == rows_b, "a rung seeded by seeking holds what playing would"
    assert {r["rung"] for r in rows_a} == {"30s", "3m", "15m"}


def test_every_rung_publishes_the_same_columns(packed):
    """Same indicators, three scales. A table template mirrors, never forks."""
    session = ReplaySession("TT", "30s")
    session.seed(600, history=300)
    q = session.subscribe()
    for _ in range(60):
        session.step()

    by_rung = {}
    for snapshot in drain(q):
        by_rung.setdefault(snapshot.rung, set()).update(snapshot.fields)
    assert len(by_rung) == 3
    assert len(set(map(frozenset, by_rung.values()))) == 1


def drop_seq(row: dict) -> dict:
    return {k: v for k, v in row.items() if k != "seq"}


def drain(q):
    out = []
    while not q.empty():
        item = q.get_nowait()
        if not isinstance(item, dict):     # transport-state frames are dicts
            out.append(item)
    return out
