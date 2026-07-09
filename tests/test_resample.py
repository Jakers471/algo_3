"""Pin the tick -> bar rebuild, and the traps it has to survive.

Three of these encode facts measured on the real tick file:

  1. 52% of ticks share a timestamp with a neighbour. A bucket's close is the
     LAST ROW of the bucket, not the row with the largest timestamp - selecting
     with idxmax on time returns the first row of a tie and silently corrupts it.
  2. Chunks end mid-bar. A partial bucket must be carried and merged, not
     emitted as if it were complete.
  3. Raw prices jump 211-270 points at each quarterly roll. Bars must be
     back-adjusted, or a strategy reads a roll as a huge move.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.data import resample


def ticks(rows) -> pd.DataFrame:
    """rows: (second, price, bid, ask, volume, adj)."""
    base = pd.Timestamp("2024-06-03 13:30:00")
    return pd.DataFrame({
        "ts": [base + pd.Timedelta(seconds=s) for s, *_ in rows],
        "price": [r[1] for r in rows],
        "bid": [r[2] for r in rows],
        "ask": [r[3] for r in rows],
        "volume": [r[4] for r in rows],
        "adj": [r[5] for r in rows],
    })


def fold(df, freq="15s", chunk=0, anchor=0.0):
    return resample._fold_chunk(df, freq, chunk, anchor)


# --- aggressor classification ----------------------------------------------

def test_trade_at_ask_is_a_buy_at_bid_is_a_sell():
    side = resample.classify(
        np.array([101.0, 100.0, 100.5]),   # price
        np.array([100.0, 100.0, 100.0]),   # bid
        np.array([101.0, 101.0, 101.0]),   # ask
    )
    assert list(side) == [1, -1, 0]        # ask, bid, between


def test_a_trade_between_bid_and_ask_joins_neither_side():
    """0 must contribute to neither buy nor sell - never be guessed into one."""
    df = ticks([(1, 100.5, 100.0, 101.0, 7, 0.0)])
    bars = resample._combine([fold(df)])
    assert bars["volume"].iloc[0] == 7
    assert bars["buy_volume"].iloc[0] == 0
    assert bars["sell_volume"].iloc[0] == 0
    assert bars["delta"].iloc[0] == 0


def test_delta_is_buy_minus_sell_and_sides_sum_to_volume():
    df = ticks([
        (1, 101.0, 100.0, 101.0, 5, 0.0),   # buy 5
        (2, 100.0, 100.0, 101.0, 3, 0.0),   # sell 3
        (3, 101.0, 100.0, 101.0, 2, 0.0),   # buy 2
    ])
    bar = resample._combine([fold(df)]).iloc[0]
    assert bar["buy_volume"] == 7 and bar["sell_volume"] == 3
    assert bar["delta"] == 4
    assert bar["volume"] == 10 == bar["buy_volume"] + bar["sell_volume"]
    assert bar["trades"] == 3


# --- the duplicate-timestamp trap -------------------------------------------

def test_close_is_the_last_row_of_a_timestamp_tie():
    """52% of real ticks tie on ts. The close is file order, not max(ts)."""
    df = ticks([
        (1, 100.0, 99.0, 100.0, 1, 0.0),
        (5, 105.0, 104.0, 105.0, 1, 0.0),   # tie
        (5, 103.0, 102.0, 103.0, 1, 0.0),   # tie - THIS is the close
    ])
    bar = resample._combine([fold(df)]).iloc[0]
    assert bar["open"] == 100.0
    assert bar["close"] == 103.0, "idxmax on ts would have picked 105.0"
    assert bar["high"] == 105.0 and bar["low"] == 100.0


# --- the chunk-boundary trap ------------------------------------------------

def test_a_bucket_split_across_chunks_is_merged_not_duplicated():
    left = ticks([(1, 100.0, 99.0, 100.0, 4, 0.0), (2, 102.0, 101.0, 102.0, 1, 0.0)])
    right = ticks([(3, 101.0, 100.0, 101.0, 2, 0.0), (4, 99.0, 99.0, 100.0, 3, 0.0)])

    bars = resample._combine([fold(left, chunk=0), fold(right, chunk=1)])
    assert len(bars) == 1, "one 15s bucket, not two"
    bar = bars.iloc[0]
    assert bar["open"] == 100.0     # first row of the FIRST chunk
    assert bar["close"] == 99.0     # last row of the LAST chunk
    assert bar["high"] == 102.0 and bar["low"] == 99.0
    assert bar["volume"] == 10 and bar["trades"] == 4


def test_a_tie_across_a_chunk_boundary_breaks_by_chunk_order():
    left = ticks([(5, 105.0, 104.0, 105.0, 1, 0.0)])
    right = ticks([(5, 103.0, 102.0, 103.0, 1, 0.0)])   # same ts, later chunk
    bar = resample._combine([fold(left, chunk=0), fold(right, chunk=1)]).iloc[0]
    assert bar["open"] == 105.0 and bar["close"] == 103.0


# --- back-adjustment --------------------------------------------------------

def test_back_adjustment_removes_the_roll_jump():
    """Raw prices jump at a roll; adjusted prices are continuous."""
    anchor = 200.0
    before = ticks([(1, 1000.0, 999.0, 1000.0, 1, 0.0)])       # old contract
    after = ticks([(20, 1250.0, 1249.0, 1250.0, 1, 200.0)])    # new one, +250 richer

    bars = resample._combine([fold(before, anchor=anchor), fold(after, chunk=1, anchor=anchor)])
    closes = bars["close"].to_numpy()
    assert closes[0] == 1200.0        # 1000 - 0   + 200
    assert closes[1] == 1250.0        # 1250 - 200 + 200  (newest keeps real price)
    assert abs(closes[1] - closes[0]) == 50.0, "the fake +250 roll jump is gone"


def test_back_adjustment_does_not_disturb_the_aggressor():
    """adj is constant within a segment, so it cancels in the bid/ask comparison."""
    df = ticks([(1, 1250.0, 1249.0, 1250.0, 5, 200.0)])        # a buy, at the ask
    bar = resample._combine([fold(df, anchor=0.0)]).iloc[0]
    assert bar["buy_volume"] == 5 and bar["sell_volume"] == 0


# --- bucketing --------------------------------------------------------------

def test_bars_are_close_stamped():
    """A tick at exactly T belongs to the bar labelled T, matching the NT8 store."""
    df = ticks([(15, 100.0, 99.0, 100.0, 1, 0.0)])   # 13:30:15 exactly
    bars = resample._combine([fold(df, freq="15s")])
    assert bars.index[0] == pd.Timestamp("2024-06-03 13:30:15")


def test_derive_folds_up_exactly():
    base = pd.DataFrame(
        {
            "open": [1.0, 2.0, 3.0, 4.0],
            "high": [9.0, 2.5, 3.5, 4.5],
            "low": [0.5, 1.5, 0.1, 3.5],
            "close": [2.0, 3.0, 4.0, 5.0],
            "volume": [10, 20, 30, 40],
            "delta": [1, -2, 3, -4],
            "buy_volume": [6, 9, 16, 18],
            "sell_volume": [4, 11, 14, 22],
            "trades": [2, 3, 4, 5],
        },
        index=pd.date_range("2024-06-03 13:30:15", periods=4, freq="15s", tz="UTC"),
    )
    out = resample.derive(base, "1m")
    assert len(out) == 1
    bar = out.iloc[0]
    assert bar["open"] == 1.0 and bar["close"] == 5.0
    assert bar["high"] == 9.0 and bar["low"] == 0.1
    assert bar["volume"] == 100 and bar["delta"] == -2
    assert bar["buy_volume"] == 49 and bar["sell_volume"] == 51
    assert bar["trades"] == 14


def test_empty_buckets_are_dropped_not_emitted_as_phantom_bars():
    """The halt and the weekend have no trades. A bar there would be a lie."""
    idx = pd.to_datetime(["2024-06-03 13:30:15", "2024-06-03 17:30:15"], utc=True)
    base = pd.DataFrame(
        {c: [1.0, 2.0] for c in ("open", "high", "low", "close")}
        | {c: [1, 2] for c in ("volume", "delta", "buy_volume", "sell_volume", "trades")},
        index=idx,
    )
    out = resample.derive(base, "1m")
    assert len(out) == 2, "the four silent hours must not become bars"
