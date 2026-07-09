"""Pin absorption: the bar closed against its own order flow.

Two things this file guards. The definition itself - green close on net selling,
or red close on net buying - and the honesty rule inherited from orderflow: a bar
that never recorded an aggressor did not "absorb nothing", so absorption refuses
rather than answering False.

This is also the first indicator that DEPENDS on another. It reads `delta` from
orderflow instead of recomputing it, which is what the registry's topological
sort exists for.
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.events.types import BarClose
from src.indicators.absorption import Absorption
from src.indicators.base import Unavailable
from src.indicators.orderflow import OrderFlow
from src.indicators.registry import Registry
from src.table import columns as table_cols

TS = pd.Timestamp("2024-06-03 13:35", tz="UTC")


def bar(open_, close, delta=None, volume=10_000):
    flow = {} if delta is None else dict(
        delta=float(delta), buy_volume=1.0, sell_volume=1.0, trades=100.0)
    return BarClose(ts=TS, open=open_, high=max(open_, close) + 1,
                    low=min(open_, close) - 1, close=close, volume=volume, **flow)


def row(event):
    """Through the registry, which is what actually produces a snapshot row."""
    return Registry([Absorption(), OrderFlow()]).update(event)   # order deliberate


# --- the dependency ---------------------------------------------------------

def test_orderflow_runs_first_even_when_registered_last():
    reg = Registry([Absorption(), OrderFlow()])
    assert [i.id for i in reg.order] == ["orderflow", "absorption"]


def test_absorption_reads_delta_rather_than_recomputing_it():
    assert Absorption().depends == ("orderflow",)
    # Fed directly with upstream, it never touches buy/sell volumes.
    out = Absorption().update(bar(100, 101), {"delta": -141.0})
    assert out["absorption"] is True


# --- the definition ---------------------------------------------------------

def test_green_close_on_net_selling_is_buy_absorption():
    """Price rose while sellers were the aggressors: someone absorbed them."""
    out = row(bar(100, 101, delta=-141))
    assert out["absorption"] is True
    assert out["absorption_side"] == "buy"


def test_red_close_on_net_buying_is_sell_absorption():
    out = row(bar(101, 100, delta=+880))
    assert out["absorption"] is True
    assert out["absorption_side"] == "sell"


def test_a_bar_that_agrees_with_its_flow_is_not_absorption():
    assert row(bar(100, 101, delta=+1185))["absorption"] is False
    assert row(bar(101, 100, delta=-1185))["absorption"] is False


def test_a_doji_cannot_absorb_because_it_has_no_direction():
    assert row(bar(100, 100, delta=-500))["absorption"] is False


def test_zero_delta_is_not_absorption_it_is_balance():
    assert row(bar(100, 101, delta=0))["absorption"] is False


# --- the honesty rule -------------------------------------------------------

def test_a_bar_with_no_order_flow_yields_None_not_False():
    """False would claim the bar absorbed nothing. None says nobody recorded it."""
    out = row(bar(100, 101))
    assert out["absorption"] is None
    assert out["absorption_side"] is None
    assert out["delta"] is None


def test_absorption_refuses_directly_when_delta_is_missing():
    with pytest.raises(Unavailable):
        Absorption().update(bar(100, 101), {"delta": None})


def test_the_table_shows_a_dash_for_a_bar_that_could_not_be_judged():
    snapshot = {"time": 0, "bar": {"open": 100.0, "close": 101.0, "volume": 1},
                "fields": row(bar(100, 101))}
    assert table_cols.cell_text("absorption", snapshot) == "-"
    assert table_cols.row_is_absorption(snapshot) is False


# --- thresholds -------------------------------------------------------------

def test_min_abs_delta_filters_trivial_disagreements(monkeypatch):
    monkeypatch.setattr("src.config.indicators.absorption.MIN_ABS_DELTA", 500.0)
    assert row(bar(100, 101, delta=-141))["absorption"] is False
    assert row(bar(100, 101, delta=-900))["absorption"] is True


def test_min_volume_filters_thin_bars(monkeypatch):
    monkeypatch.setattr("src.config.indicators.absorption.MIN_VOLUME", 5_000.0)
    assert row(bar(100, 101, delta=-141, volume=100))["absorption"] is False
    assert row(bar(100, 101, delta=-141, volume=9_000))["absorption"] is True


def test_min_delta_ratio_requires_the_disagreement_to_be_material(monkeypatch):
    monkeypatch.setattr("src.config.indicators.absorption.MIN_DELTA_RATIO", 0.05)
    # 141 of 10,000 is 1.4% - noise.
    assert row(bar(100, 101, delta=-141, volume=10_000))["absorption"] is False
    # 800 of 10,000 is 8%.
    assert row(bar(100, 101, delta=-800, volume=10_000))["absorption"] is True


# --- the drawing ------------------------------------------------------------

def test_buy_absorption_is_marked_below_the_bar_and_sell_above():
    from src.chart import overlays

    buy = overlays.marks_for(1_000, {"absorption": True, "absorption_side": "buy"})
    sell = overlays.marks_for(1_000, {"absorption": True, "absorption_side": "sell"})
    assert buy[0]["position"] == "belowBar", "the resting buyer is under the bar"
    assert sell[0]["position"] == "aboveBar"
    assert buy[0]["kind"] == "marker" and sell[0]["kind"] == "marker"


def test_no_marker_for_a_bar_that_did_not_absorb():
    from src.chart import overlays

    assert overlays.marks_for(1_000, {"absorption": False}) == []
    assert overlays.marks_for(1_000, {"absorption": None}) == []


def test_markers_group_into_their_own_overlay_spec():
    from src.chart import overlays

    marks = overlays.marks_for(1_000, {"absorption": True, "absorption_side": "buy"})
    specs = overlays.group_marks(marks)
    assert [s["kind"] for s in specs] == ["markers"]
    assert specs[0]["id"] == "absorption"
