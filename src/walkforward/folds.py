"""Generate walk-forward IS/OOS window folds over a bar index.

One job: given the data's date span and the window sizes, produce the list of
(in-sample, out-of-sample) date windows. Rolling by default (fixed IS window
slides); anchored keeps the IS start fixed and grows it. OOS windows are
consecutive and non-overlapping when step == oos_days.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class Fold:
    num: int
    is_start: pd.Timestamp
    is_end: pd.Timestamp      # == oos_start (half-open [is_start, is_end))
    oos_start: pd.Timestamp
    oos_end: pd.Timestamp


def generate(
    index: pd.DatetimeIndex,
    is_days: int,
    oos_days: int,
    step_days: int,
    anchored: bool = False,
) -> list[Fold]:
    """Build the fold windows spanning ``index`` (only full OOS windows are kept)."""
    data_start, data_end = index[0], index[-1]
    is_td = pd.Timedelta(days=is_days)
    oos_td = pd.Timedelta(days=oos_days)
    step = pd.Timedelta(days=step_days)

    folds: list[Fold] = []
    oos_start = data_start + is_td
    num = 1
    while oos_start + oos_td <= data_end:
        is_start = data_start if anchored else oos_start - is_td
        folds.append(Fold(num, is_start, oos_start, oos_start, oos_start + oos_td))
        oos_start += step
        num += 1
    return folds
