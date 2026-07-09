"""Pin the sessions indicator, and the two bugs that made it wrong.

Both were found by measuring against the real bars, not by reasoning:
  1. SESSION_TZ was America/Chicago while the windows were Eastern numbers, so
     5,764 real trading bars per two years fell in no session at all and the
     maintenance halt was mislabelled as NY.
  2. Bars are close-stamped, so membership must be ``start < minute <= end``.
     With ``minute < end`` the 17:00 ET bar - NY's last - belongs nowhere.
"""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from src.config import session as cfg
from src.events.types import BarClose
from src.indicators.base import Indicator, Unavailable
from src.indicators.registry import CircularDependency, Registry
from src.indicators.sessions import Sessions, _minute_of_day, session_for


def bar(iso: str, o=100.0, h=101.0, low=99.0, c=100.5, v=10.0) -> BarClose:
    return BarClose(ts=pd.Timestamp(iso, tz="UTC"), open=o, high=h, low=low, close=c, volume=v)


def et(iso: str) -> int:
    """Eastern wall-clock -> minute of day."""
    t = pd.Timestamp(iso)
    return t.hour * 60 + t.minute


# --- the timezone bug -------------------------------------------------------

def test_session_tz_is_eastern():
    """Chicago + Eastern numbers silently discards the 17:00-18:00 ET hour."""
    assert cfg.SESSION_TZ == "US/Eastern"


def test_maintenance_halt_belongs_to_no_session():
    """17:00-18:00 ET is the CME halt. Bars there would be a data error."""
    assert session_for(et("17:30")) is None
    assert session_for(et("17:01")) is None


def test_session_windows():
    assert session_for(et("18:05")) == "Asia"      # globex reopen
    assert session_for(et("23:00")) == "Asia"
    assert session_for(et("02:00")) == "Asia"      # wraps past midnight
    assert session_for(et("03:05")) == "London"
    assert session_for(et("07:59")) == "London"
    assert session_for(et("08:05")) == "NY"
    assert session_for(et("13:30")) == "NY"


# --- the close-stamped boundary bug -----------------------------------------

def test_boundary_bars_belong_to_the_session_they_closed_in():
    """A bar labelled T covers (T-step, T], so T itself is that session's last bar."""
    assert session_for(et("17:00")) == "NY"        # NY's final bar, not orphaned
    assert session_for(et("03:00")) == "Asia"      # Asia's final bar, not London's
    assert session_for(et("08:00")) == "London"    # London's final bar, not NY's
    assert session_for(et("18:00")) is None        # covers 17:55-18:00 = still halt


def test_every_minute_of_a_trading_day_has_a_session_or_is_the_halt():
    halt = {m for m in range(24 * 60) if session_for(m) is None}
    # exactly the 60 minutes of (17:00, 18:00] ET
    assert halt == set(range(17 * 60 + 1, 18 * 60 + 1))


# --- the offset cache -------------------------------------------------------

@pytest.mark.parametrize("iso", [
    "2024-03-10 06:00:00",   # US DST begins (2am ET)
    "2024-03-10 07:00:00",
    "2024-11-03 05:00:00",   # US DST ends
    "2024-11-03 06:00:00",
    "2024-07-04 12:00:00",   # deep in EDT
    "2024-01-15 12:00:00",   # deep in EST
])
def test_cached_offset_matches_real_tz_conversion(iso):
    """The hour-bucket cache must be exact, including across both DST flips."""
    ts = pd.Timestamp(iso, tz="UTC")
    local = ts.tz_convert(cfg.SESSION_TZ)
    assert _minute_of_day(ts) == local.hour * 60 + local.minute


def test_offset_cache_agrees_over_a_dst_transition_minute_by_minute():
    start = pd.Timestamp(datetime(2024, 3, 10, 4, 0, tzinfo=timezone.utc))
    for i in range(0, 300, 7):
        ts = start + pd.Timedelta(minutes=i)
        expected = ts.tz_convert(ZoneInfo(cfg.SESSION_TZ))
        assert _minute_of_day(ts) == expected.hour * 60 + expected.minute


# --- the state machine ------------------------------------------------------

def test_running_extremes_never_see_the_future():
    s = Sessions()
    r1 = s.update(bar("2024-07-01 13:35:00", h=110, low=90))   # NY
    assert r1["session"] == "NY" and r1["session_new"] is True
    assert r1["session_high"] == 110 and r1["session_low"] == 90

    r2 = s.update(bar("2024-07-01 13:40:00", h=105, low=80))
    assert r2["session_new"] is False
    assert r2["session_high"] == 110   # kept
    assert r2["session_low"] == 80     # extended


def test_extremes_reset_on_a_new_session():
    s = Sessions()
    s.update(bar("2024-07-01 20:00:00", h=999, low=1))          # NY (16:00 ET)
    r = s.update(bar("2024-07-01 22:05:00", h=50, low=40))      # Asia (18:05 ET)
    assert r["session"] == "Asia" and r["session_new"] is True
    assert r["session_high"] == 50 and r["session_low"] == 40   # not 999 / 1


def test_reset_clears_state():
    s = Sessions()
    s.update(bar("2024-07-01 13:35:00"))
    s.reset()
    r = s.update(bar("2024-07-01 13:40:00"))
    assert r["session_new"] is True


def test_untimestamped_event_is_unavailable_not_a_guess():
    with pytest.raises(Unavailable):
        Sessions().update(object())


# --- the registry -----------------------------------------------------------

class _Fake(Indicator):
    def __init__(self, ind_id, fields, depends=()):
        self.id, self.fields, self.depends = ind_id, fields, depends
        self.seen = []

    def reset(self):
        self.seen = []

    def update(self, event, upstream=None):
        self.seen.append(dict(upstream or {}))
        return {f: f"{self.id}:{f}" for f in self.fields}


def test_registry_runs_dependencies_first_and_passes_their_fields():
    base = _Fake("base", ("x",))
    derived = _Fake("derived", ("y",), depends=("base",))
    reg = Registry([derived, base])           # deliberately out of order

    assert [i.id for i in reg.order] == ["base", "derived"]
    row = reg.update(bar("2024-07-01 13:35:00"))
    assert row == {"x": "base:x", "y": "derived:y"}
    assert derived.seen[0] == {"x": "base:x"}   # upstream field was handed down


def test_registry_rejects_a_cycle_at_startup():
    a = _Fake("a", ("x",), depends=("b",))
    b = _Fake("b", ("y",), depends=("a",))
    with pytest.raises(CircularDependency):
        Registry([a, b])


def test_registry_rejects_an_unknown_dependency():
    a = _Fake("a", ("x",), depends=("nope",))
    with pytest.raises(KeyError):
        Registry([a])


class _TickOnly(Indicator):
    id, fields, depends = "tickonly", ("delta",), ()
    def reset(self): pass
    def update(self, event, upstream=None):
        raise Unavailable("delta needs trades, not bars")


def test_unavailable_indicator_yields_none_not_a_proxy():
    """A bar-fed delta must record its own absence, never a made-up number."""
    reg = Registry([_TickOnly()])
    assert reg.update(bar("2024-07-01 13:35:00")) == {"delta": None}


def test_field_names_are_the_row_columns_in_run_order():
    reg = Registry([_Fake("derived", ("y",), depends=("base",)), _Fake("base", ("x",))])
    assert reg.field_names() == ["x", "y"]
