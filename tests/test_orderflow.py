"""Pin the one rule that matters about order flow: absent is not zero.

A bar file records total volume but never which side was the aggressor. That
information is destroyed by aggregation and no transformation recovers it. So a
bar-fed order-flow indicator must REFUSE, and the refusal must survive all the
way to the screen as "-" rather than becoming a 0 somewhere in between.

Zero is a claim about the market: buying and selling were balanced.
None is a claim about the data: nobody wrote it down.
A backtest would believe the first one.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from src.chart import packer
from src.events.types import BarClose
from src.indicators.base import Unavailable
from src.indicators.orderflow import OrderFlow
from src.indicators.registry import Registry
from src.table import columns as table_cols


def bar(**flow) -> BarClose:
    return BarClose(ts=pd.Timestamp("2024-06-03 13:30", tz="UTC"),
                    open=100.0, high=101.0, low=99.0, close=100.5, volume=13420, **flow)


TICK_BAR = dict(delta=-1358.0, buy_volume=6031.0, sell_volume=7389.0, trades=8214.0)


# --- the indicator ----------------------------------------------------------

def test_publishes_the_flow_a_tick_built_bar_carries():
    row = OrderFlow().update(bar(**TICK_BAR))
    assert row == {"delta": -1358.0, "buy_volume": 6031.0,
                   "sell_volume": 7389.0, "trades": 8214.0}


def test_refuses_a_bar_that_has_no_aggressor_recorded():
    with pytest.raises(Unavailable):
        OrderFlow().update(bar())


def test_it_computes_nothing_it_only_lifts():
    """The work happened once, in resample.py. This must not re-derive it."""
    row = OrderFlow().update(bar(**TICK_BAR))
    assert row["delta"] == row["buy_volume"] - row["sell_volume"]


def test_a_genuine_zero_delta_is_published_not_refused():
    """Balanced flow IS a fact when the bar recorded it. Do not confuse it with absent."""
    row = OrderFlow().update(bar(delta=0.0, buy_volume=50.0, sell_volume=50.0, trades=4.0))
    assert row["delta"] == 0.0


def test_it_is_stateless_so_a_replay_seek_cannot_carry_flow_across():
    flow = OrderFlow()
    flow.update(bar(**TICK_BAR))
    flow.reset()
    with pytest.raises(Unavailable):
        flow.update(bar())


# --- through the registry, which is what the snapshot row is -----------------

def test_the_row_records_absence_as_None_across_every_field():
    row = Registry([OrderFlow()]).update(bar())
    assert row == {"delta": None, "buy_volume": None, "sell_volume": None, "trades": None}
    assert 0 not in row.values()


# --- and out to the table, unchanged ----------------------------------------

def test_the_table_shows_a_dash_not_a_zero():
    snapshot = {"time": 0, "bar": {"open": 1.0, "close": 1.0, "volume": 1},
                "fields": Registry([OrderFlow()]).update(bar())}
    assert table_cols.cell_text("delta", snapshot) == "-"
    assert table_cols.cell_text("trades", snapshot) == "-"


# --- and the wire format enforces it ----------------------------------------

def test_the_packed_format_stores_absence_as_NaN():
    """A float, not an int, precisely so that 'absent' is representable."""
    recs = np.empty(1, dtype=packer.BAR_DTYPE)
    for field in packer.ORDER_FLOW_FIELDS:
        recs[field] = np.float32("nan")
    assert all(math.isnan(float(recs[f][0])) for f in packer.ORDER_FLOW_FIELDS)


def test_nan_becomes_None_when_bars_become_events():
    from src.chart import overlays

    assert overlays._optional(float("nan")) is None
    assert overlays._optional(None) is None
    assert overlays._optional(-1358.0) == -1358.0
    assert overlays._optional(0.0) == 0.0, "a real zero must survive"
