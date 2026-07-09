"""Pin the chart's wire format and its slicing/locating contract.

The browser decodes bars by walking raw bytes at fixed offsets, so a silent
change to BAR_DTYPE would corrupt every candle rather than raise. These tests
hold the record layout still and check the two questions store.py answers.
"""

from __future__ import annotations

import json

import numpy as np
import pytest

from src.chart import api, packer, store


@pytest.fixture
def packed(tmp_path, monkeypatch):
    """A tiny hand-built cache, so nothing here depends on the real Parquet."""
    monkeypatch.setattr("src.config.chart.CACHE_DIR", tmp_path)
    # store memoizes memmaps per (symbol, timeframe) for the process lifetime.
    store._BARS.clear()
    store._TIMES.clear()
    store._META.clear()

    n = 10
    recs = np.empty(n, dtype=packer.BAR_DTYPE)
    recs["time"] = np.arange(1_000_000, 1_000_000 + n * 300, 300, dtype="<u4")
    recs["open"] = np.arange(n) + 5000.25
    recs["high"] = np.arange(n) + 5001.50
    recs["low"] = np.arange(n) + 4999.00
    recs["close"] = np.arange(n) + 5000.75
    recs["volume"] = np.arange(n) * 10

    bars_fp, times_fp, meta_fp = packer.paths_for("XX", "5m")
    recs.tofile(bars_fp)
    recs["time"].astype(packer.TIME_DTYPE).tofile(times_fp)
    meta_fp.write_text(json.dumps({
        "format_version": packer.FORMAT_VERSION, "symbol": "XX", "timeframe": "5m",
        "count": n, "bar_bytes": packer.BAR_DTYPE.itemsize,
        "first_time": int(recs["time"][0]), "last_time": int(recs["time"][-1]),
    }))
    return recs


def test_bar_record_is_24_bytes():
    """The JS decoder hard-codes this stride; changing it breaks the chart."""
    assert packer.BAR_DTYPE.itemsize == 24
    assert [name for name in packer.BAR_DTYPE.names] == [
        "time", "open", "high", "low", "close", "volume",
    ]


def test_quarter_tick_prices_survive_float32():
    """Futures trade in quarter ticks; f4 must carry them exactly, not nearly."""
    prices = np.array([5727.25, 20000.75, 6000.50, 1234.25], dtype="<f4")
    assert list(prices.astype(np.float64)) == [5727.25, 20000.75, 6000.50, 1234.25]


def test_slice_returns_exact_bytes(packed):
    body, start = store.slice_bytes("XX", "5m", 2, 3)
    assert start == 2
    assert len(body) == 3 * 24
    out = np.frombuffer(body, dtype=packer.BAR_DTYPE)
    assert list(out["time"]) == list(packed["time"][2:5])
    assert list(out["close"]) == list(packed["close"][2:5])


def test_slice_clamps_past_the_end(packed):
    """Walking off the right edge of a replay is an empty answer, not an error."""
    body, start = store.slice_bytes("XX", "5m", 8, 100)
    assert start == 8
    assert len(body) == 2 * 24

    body, start = store.slice_bytes("XX", "5m", 999, 10)
    assert start == 10 and body == b""


def test_slice_clamps_negative_start(packed):
    body, start = store.slice_bytes("XX", "5m", -5, 2)
    assert start == 0 and len(body) == 2 * 24


def test_locate_finds_first_bar_at_or_after(packed):
    assert store.locate("XX", "5m", 1_000_000) == 0
    assert store.locate("XX", "5m", 1_000_900) == 3      # exact hit
    assert store.locate("XX", "5m", 1_000_800) == 3      # between bars -> next
    assert store.locate("XX", "5m", 0) == 0              # before data -> first
    assert store.locate("XX", "5m", 9_999_999) == 9      # after data -> last


def test_count_and_datasets(packed, monkeypatch):
    monkeypatch.setattr("src.config.chart.SYMBOLS", ("XX",))
    monkeypatch.setattr("src.config.chart.TIMEFRAMES", ("5m",))
    assert store.count("XX", "5m") == 10
    assert store.datasets() == {"XX": {"5m": {
        "count": 10, "first_time": 1_000_000, "last_time": 1_002_700,
    }}}


def test_missing_dataset_is_404_not_a_crash(packed):
    status, _, body, _ = api.handle("/api/bars", {
        "symbol": ["ZZ"], "timeframe": ["5m"], "start": ["0"], "count": ["10"],
    })
    assert status == 404
    assert "no packed chart cache" in json.loads(body)["error"].lower()


def test_bad_query_is_400(packed):
    status, _, body, _ = api.handle("/api/bars", {"symbol": ["XX"]})
    assert status == 400
    assert "timeframe" in json.loads(body)["error"]

    status, _, body, _ = api.handle("/api/bars", {
        "symbol": ["XX"], "timeframe": ["5m"], "start": ["abc"],
    })
    assert status == 400


def test_request_size_is_capped(packed, monkeypatch):
    """A client asking for six million bars must not be handed six million bars."""
    monkeypatch.setattr("src.config.chart.MAX_BARS_PER_REQUEST", 4)
    _, _, body, headers = api.handle("/api/bars", {
        "symbol": ["XX"], "timeframe": ["5m"], "start": ["0"], "count": ["999999"],
    })
    assert len(body) == 4 * 24
    assert headers["X-Count"] == "4"
    assert headers["X-Total"] == "10"
