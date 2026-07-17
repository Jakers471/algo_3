"""Pins the seal: the vault's boundary, its receipt, and the catalog that obeys it.

The one property that matters: the boundary between explore and sealed cannot
move quietly. The declaration (config SEALED_FROM) and the receipt
(SESSION_SPLIT.json) are checked against each other on every load, the label
rule is exact at the boundary, and the catalog's default output physically
cannot contain a sealed row.
"""

from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
import pytest

from src.config import session_history as cfg
from src.session_history import split


@pytest.fixture(autouse=True)
def fresh_cache():
    """split caches the receipt; each test starts clean and leaves clean."""
    split._CACHE = None
    yield
    split._CACHE = None


# --- the receipt ---------------------------------------------------------------

def test_the_receipt_exists_and_is_internally_consistent():
    data = split.load()
    assert data["explore"]["count"] + data["sealed"]["count"] == data["sessions_total"]
    assert data["sealed_from"] == cfg.SEALED_FROM.isoformat()


def test_the_cutoff_is_the_declared_date_at_midnight_utc():
    declared = dt.datetime(cfg.SEALED_FROM.year, cfg.SEALED_FROM.month,
                           cfg.SEALED_FROM.day, tzinfo=dt.timezone.utc)
    assert split.cutoff() == int(declared.timestamp())


def test_the_label_rule_is_exact_at_the_boundary():
    assert split.label(split.cutoff() - 1) == split.EXPLORE
    assert split.label(split.cutoff()) == split.SEALED
    assert split.is_sealed(split.cutoff())
    assert not split.is_sealed(split.cutoff() - 1)


def test_drift_between_declaration_and_receipt_is_a_loud_error(monkeypatch):
    """The whole point of two artifacts: neither can move without the other noticing."""
    monkeypatch.setattr(cfg, "SEALED_FROM", dt.date(2030, 1, 1))
    with pytest.raises(split.SealDrift):
        split.load()


# --- the catalog obeys the seal --------------------------------------------------

def _ny_bars(day: str, n: int = 8) -> pd.DataFrame:
    """A run of 5m bars inside the NY session (13:05 UTC is 09:05 ET in summer)."""
    idx = pd.date_range(f"{day} 13:05", periods=n, freq="5min", tz="UTC")
    return pd.DataFrame({
        "open": np.linspace(100, 101, n), "high": np.linspace(101, 102, n),
        "low": np.linspace(99, 100, n), "close": np.linspace(100.5, 101.5, n),
        "volume": np.full(n, 50.0), "delta": np.full(n, 5.0),
    }, index=idx)


def _asia_bar(day: str) -> pd.DataFrame:
    """One bar in Asia (22:05 UTC), untracked - it breaks the NY run in two."""
    idx = pd.date_range(f"{day} 22:05", periods=1, freq="5min", tz="UTC")
    return pd.DataFrame({"open": [100.0], "high": [101.0], "low": [99.0],
                         "close": [100.0], "volume": [50.0], "delta": [0.0]}, index=idx)


@pytest.fixture()
def cache_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(cfg, "CACHE_DIR", tmp_path)
    return tmp_path


def test_the_default_catalog_physically_excludes_sealed_sessions(cache_dir):
    from src.session_history import catalog

    bars = pd.concat([_ny_bars("2024-06-05"), _asia_bar("2024-06-05"),
                      _ny_bars("2026-06-03")])
    written = catalog.build_catalog("X", "5m", bars=bars, with_vap=False)

    assert set(written) == {split.EXPLORE}
    frame = pd.read_parquet(written[split.EXPLORE]["path"])
    assert (frame["split"] == split.EXPLORE).all()
    assert frame["session_id"].nunique() == 1
    assert pd.to_datetime(frame["time"].max(), unit="s").year == 2024


def test_include_sealed_writes_the_vault_to_its_own_file(cache_dir):
    from src.session_history import catalog

    bars = pd.concat([_ny_bars("2024-06-05"), _asia_bar("2024-06-05"),
                      _ny_bars("2026-06-03")])
    written = catalog.build_catalog("X", "5m", bars=bars, with_vap=False,
                                    include_sealed=True)

    assert set(written) == {split.EXPLORE, split.SEALED}
    assert written[split.EXPLORE]["path"] != written[split.SEALED]["path"]
    sealed = pd.read_parquet(written[split.SEALED]["path"])
    assert (sealed["split"] == split.SEALED).all()
    assert pd.to_datetime(sealed["time"].min(), unit="s").year == 2026


def test_catalog_rows_carry_the_card_not_the_percentiles(cache_dir):
    """The percentile fields are derived FROM this distribution - carrying the
    shipped full-dataset table's numbers into explore rows would leak the vault."""
    from src.session_history import catalog

    bars = _ny_bars("2024-06-05")
    written = catalog.build_catalog("X", "5m", bars=bars, with_vap=False)
    frame = pd.read_parquet(written[split.EXPLORE]["path"])

    assert "session_net_ratio" in frame.columns
    assert "session_efficiency_recent" in frame.columns
    assert "session_range_percentile" not in frame.columns
    assert "session_travel_budget" not in frame.columns
    assert len(frame) == 8    # one row per bar of the one explore session
    assert list(frame["session_bars"]) == list(range(1, 9))
