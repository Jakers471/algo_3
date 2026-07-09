"""Pins the volume profile indicator: one developing range, frozen onto each structure.

Two claims worth protecting.

The freeze happens at the bar that MADE the swing, not the later bar that proved
it - the same rule every structure indicator obeys, and the reason a leg is an
interval in time rather than a claim about the future.

And a warmup walk skips the value area but never the freeze. Only the newest
profile is ever drawn, so computing 4,999 of them is waste; but every one of them
that CLOSED is kept, because those are the profiles that stay on the chart.
"""

from __future__ import annotations

import datetime as dt

import numpy as np
import pytest

from src.config.indicators import profile as pcfg
from src.events.types import BarClose
from src.indicators.base import Unavailable
from src.indicators.profile import Profile

START = dt.datetime(2024, 3, 13, 14, 0, tzinfo=dt.timezone.utc)


def vbar(i, levels=((100.0, 10, 5),)):
    prices = np.array([p for p, _, _ in levels])
    vol = np.array([v for _, v, _ in levels], dtype=np.int64)
    buy = np.array([b for _, _, b in levels], dtype=np.int64)
    mid = float(prices[0])
    return BarClose(ts=START + dt.timedelta(minutes=5 * i), open=mid, high=mid,
                    low=mid, close=mid, volume=float(vol.sum()), vap=(prices, vol, buy))


def at(i: int) -> int:
    return int(vbar(i).ts.timestamp())


def up(swing=None, price=None, time=None, scale=8.0):
    row = {"range_scale": scale, "swing": swing}
    if swing:
        row["swing_price"] = price
        row["swing_time"] = time
    return row


# --- refusals ----------------------------------------------------------------

def test_a_bar_with_no_volume_at_price_is_refused_not_guessed():
    """A bar file knows its total volume and its range. Not where inside it."""
    bare = BarClose(ts=START, open=1, high=2, low=0, close=1, volume=10)
    with pytest.raises(Unavailable, match="volume at price"):
        Profile().update(bare, up())


def test_without_a_scale_there_is_no_bin_width():
    with pytest.raises(Unavailable, match="range_scale"):
        Profile().update(vbar(0), {"range_scale": None})


# --- the developing range ----------------------------------------------------

def test_the_developing_range_grows_every_bar():
    p = Profile()
    p.update(vbar(0, levels=((100.0, 10, 5),)), up())
    row = p.update(vbar(1, levels=((100.0, 10, 5),)), up())
    assert row["profile_volume"] == 20
    assert row["profile_from_time"] == at(0) and row["profile_to_time"] == at(1)


def test_a_confirmed_swing_freezes_the_range_and_starts_a_new_one():
    """The split is at the bar that MADE the swing, not the one that proved it."""
    p = Profile()
    p.update(vbar(0, levels=((100.0, 10, 5),)), up())
    p.update(vbar(1, levels=((100.0, 10, 5),)), up())

    # Bar 2 confirms a swing that bar 1 made. Bars 0-1 close; bar 2 opens the next.
    row = p.update(vbar(2, levels=((100.0, 7, 7),)), up("high", 100.0, at(1)))

    assert row["profile_volume"] == 7, "the new range holds only the confirming bar"
    assert row["profile_from_time"] == at(2)

    closed = row["profile_closed"]
    assert len(closed) == 1
    assert closed[0]["volume"] == 20, "the frozen range holds bars 0 and 1"
    assert (closed[0]["from_time"], closed[0]["to_time"]) == (at(0), at(1))


def test_a_closed_profile_keeps_the_span_it_described():
    """It is drawn against its own structure, not against the right edge."""
    p = Profile()
    p.update(vbar(0), up())
    p.update(vbar(1), up())
    p.update(vbar(2), up("high", 100.0, at(1)))
    for i in range(3, 8):
        row = p.update(vbar(i), up())

    assert row["profile_closed"][0]["to_time"] == at(1), "frozen where the swing was made"
    assert row["profile_to_time"] == at(7), "the developing one still tracks now"


def test_only_the_last_few_closed_profiles_are_kept(monkeypatch):
    """Ninety histograms would be nine thousand segments nobody can read."""
    monkeypatch.setattr(pcfg, "MAX_CLOSED", 2)
    p = Profile()
    row = None
    for i in range(0, 12, 2):
        p.update(vbar(i), up())
        row = p.update(vbar(i + 1), up("high", 100.0, at(i)))
    assert len(row["profile_closed"]) == 2


def test_warmup_skips_the_summary_but_never_the_freeze():
    """Only the newest profile is drawn, so a warmup bar computes nothing.

    Not even the closed list is published: copying six histograms into a row that
    is thrown away is the same waste as computing a value area for it. The FREEZE
    still happens - those profiles are the ones that stay on the chart - and the
    first non-quiet bar hands them over.
    """
    p = Profile()
    p.quiet = True
    p.update(vbar(0), up())
    p.update(vbar(1), up())
    row = p.update(vbar(2), up("high", 100.0, at(1)))
    assert row["profile_poc"] is None, "no value area is computed while quiet"
    assert row["profile_closed"] is None, "nor is a row nobody reads filled in"
    assert len(p._closed) == 1, "but the range froze all the same"

    p.quiet = False
    row = p.update(vbar(3), up())
    assert row["profile_poc"] is not None
    assert len(row["profile_closed"]) == 1, "and the frozen one is handed over"


def test_bins_are_sized_in_range_scale_not_in_points(monkeypatch):
    monkeypatch.setattr(pcfg, "BINS_PER_SCALE", 1)
    levels = tuple((100.0 + 0.25 * i, 1, 1) for i in range(40))   # spans 10 points

    quiet = Profile().update(vbar(0, levels=levels), up(scale=2.0))
    loud = Profile().update(vbar(0, levels=levels), up(scale=20.0))
    assert len(quiet["profile_bins"]) > len(loud["profile_bins"]), (
        "a loud market gets wider bins, so the histogram's shape stays comparable")


# --- drawing: a bin is a segment, and the layer is redrawn wholesale ----------

def profile_row(bins, poc=100.0, closed=None):
    return {"profile_bins": bins, "profile_from_time": 1000, "profile_to_time": 2000,
            "profile_poc": poc, "profile_val": 99.0, "profile_vah": 101.0,
            "profile_closed": closed}


def test_a_profile_needs_no_new_chart_shape():
    from src.chart import overlays
    marks = overlays.marks_for(2000, profile_row([[100.0, 10, 8], [101.0, 5, 1]]))
    assert all(m["kind"] == "segment" for m in marks)
    assert all(m["layer"] == "profile" for m in marks)


def test_a_bin_is_coloured_by_who_crossed_the_spread():
    from src.chart import overlays
    marks = overlays.marks_for(2000, profile_row([[100.0, 10, 9], [101.0, 10, 1]]))
    assert marks[0]["color"] == pcfg.BUY_COLOR
    assert marks[1]["color"] == pcfg.SELL_COLOR


def test_a_bin_anchors_both_ends_to_a_real_bar_and_offsets_in_pixels():
    """An interpolated timestamp has no x coordinate, so the bin would vanish.

    lightweight-charts maps a time to a coordinate by finding it in the series.
    A moment no bar occupies returns null, and segments.js skips any polyline
    with a corner it cannot place - so every bin was silently invisible.
    """
    from src.chart import overlays
    marks = overlays.marks_for(2000, profile_row([[100.0, 10, 5], [101.0, 5, 2]]))
    for mark in marks[:2]:
        left, right = mark["points"]
        assert left["time"] == right["time"] == 2000, "both ends name the same real bar"
        assert right["dx"] == 0 and left["dx"] < 0, "the left end is pushed back in pixels"

    lengths = [-m["points"][0]["dx"] for m in marks[:2]]
    assert lengths[0] > lengths[1], "the heaviest bin is the longest"
    assert lengths[0] == pytest.approx(pcfg.MAX_WIDTH_PX)


CLOSED = [{"poc": 50.0, "val": 49.0, "vah": 51.0, "from_time": 100,
           "to_time": 500, "volume": 30, "bins": [[50.0, 30, 30]]}]


def test_a_closed_profile_is_drawn_at_its_own_range_and_dimmer():
    from src.chart import overlays
    marks = overlays.marks_for(2000, profile_row([[100.0, 10, 8]], closed=CLOSED))

    bar = next(m for m in marks
               if m["points"][0]["price"] == 50.0 and m["points"][0]["dx"] < 0)
    assert bar["points"][0]["time"] == 500, "anchored at ITS right edge, not at now"
    assert bar["color"] == pcfg.CLOSED_BUY_COLOR
    assert -bar["points"][0]["dx"] == pytest.approx(pcfg.CLOSED_WIDTH_PX)

    poc = next(m for m in marks if m["color"] == pcfg.CLOSED_POC_COLOR)
    assert [p["time"] for p in poc["points"]] == [100, 500], "spans the range it describes"


def test_closed_profiles_draw_even_when_the_developing_one_cannot():
    from src.chart import overlays
    row = {"profile_bins": None, "profile_closed": CLOSED}
    assert overlays.marks_for(2000, row), "history does not vanish while warming up"


def test_a_layer_is_replaced_wholesale_so_a_shrinking_profile_leaves_no_ghosts():
    from src.chart import overlays

    wide = overlays.marks_for(2000, profile_row([[100.0, 9, 5], [101.0, 9, 5], [102.0, 9, 5]]))
    narrow = overlays.marks_for(3000, profile_row([[100.0, 9, 5]]))
    kept = overlays.collapse_redrawn(wide + narrow)

    assert all(m["at"] == 3000 for m in kept), "only the newest emission survives"
    assert len(kept) == len(narrow), "the wider profile's surplus bins are gone"
