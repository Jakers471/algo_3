"""Build the session catalog: the card, every explore session, every bar.

One job: walk a dataset once through the REAL indicators (Sessions ->
RangeScale -> SessionStats - the same code the chart and replay run, never a
reimplementation) and write one parquet row per bar of every London/NY
session, labelled explore/sealed by the committed seal.

This is the foundation the interrogation and the k-NN sit on. Three jobs in
one artifact:

- It is the percentile-vs-history idea in raw form: every (session, elapsed
  bar) cell's full distribution, not just its breakpoints.
- It turns every N=1 anecdote into a population. "Does range expansion with
  rising efficiency separate real breaks from traps" stops being an argument
  from three eyeballed sessions and becomes a query over ~65k explore rows.
- Description is free. Looking at explore distributions burns no degrees of
  freedom; only decisions do.

**The vault is enforced here, not by discipline.** The default build refuses
to include sealed sessions - `include_sealed=True` exists for the one honest
final evaluation of an already-frozen rule, and writes to a separate,
loudly-named file so sealed rows can never sneak into an explore analysis by
sharing a path.

The percentile fields are deliberately ABSENT from the catalog: SessionStats
is constructed without a symbol/timeframe, so they publish None and are
dropped. They are derived numbers - the catalog is the raw distribution they
are derived FROM - and the shipped percentile table was built over the full
dataset including sealed sessions, so carrying those numbers into explore
rows would leak the vault's shape into every analysis.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from src.config import session_history as cfg
from src.config.indicators import profile as profile_cfg
from src.config.indicators import session_stats as ss_cfg
from src.data.loader import load_raw
from src.events.types import BarClose
from src.indicators.range_scale import RangeScale
from src.indicators.registry import Registry
from src.indicators.session_stats import SessionStats
from src.indicators.sessions import Sessions, _minute_of_day, session_for
from src.profile import store as vap_store

logger = logging.getLogger(__name__)

# The card's scalar readings, in table order. Payload fields (bins, hvn/lvn
# lists) and the percentile fields (absent by construction, see module doc)
# are not columns; hvn/lvn ride along as counts.
_SCALARS = (
    "session_bars", "range_scale",
    "session_range", "session_net", "session_net_ratio", "session_closed_ratio",
    "session_efficiency_recent", "session_efficiency_prior",
    "session_range_ratio", "session_volume_ratio", "session_dir_change_rate",
    "session_high_at_ratio", "session_low_at_ratio",
    "session_volume", "session_delta_recent",
    "session_poc", "session_poc_ratio", "session_val", "session_vah",
)


def path(symbol: str, timeframe: str, split_label: str):
    cfg.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return cfg.CACHE_DIR / f"catalog_{symbol}_{timeframe}_{split_label}.parquet"


def _optional(value) -> float | None:
    return None if value is None or (isinstance(value, float) and np.isnan(value)) else float(value)


def build_catalog(symbol: str, timeframe: str, *, include_sealed: bool = False,
                  bars: pd.DataFrame | None = None, with_vap: bool = True,
                  progress=None) -> dict:
    """Walk the dataset once; write the explore catalog (and optionally the sealed one).

    ``bars``/``with_vap`` exist for tests: synthetic bars, no volume-at-price
    store. Production callers pass neither.
    """
    from src.session_history import split

    if bars is None:
        bars = load_raw(symbol, timeframe)
    step = _step_seconds(timeframe)
    tracked = set(ss_cfg.TRACKED_SESSIONS)

    registry = Registry([Sessions(), RangeScale(), SessionStats()])
    o, h = bars["open"].to_numpy(), bars["high"].to_numpy()
    lo, c = bars["low"].to_numpy(), bars["close"].to_numpy()
    v = bars["volume"].to_numpy()
    d = bars["delta"].to_numpy() if "delta" in bars.columns else np.full(len(bars), np.nan)

    rows: list[dict] = []
    session_id: int | None = None
    session_label: str | None = None

    for i, ts in enumerate(bars.index):
        epoch = int(ts.timestamp())
        # session_for is pure (no state), so the vap fetch can be decided
        # BEFORE the event exists - the indicator itself is fed exactly once.
        in_scope = session_for(_minute_of_day(ts)) in tracked
        vap = None
        if in_scope and with_vap:
            try:
                vap = vap_store.histogram(symbol, profile_cfg.BASE_TIMEFRAME,
                                          epoch - step, epoch)
            except vap_store.NotBuilt:
                vap = None

        # Python floats, never numpy scalars: every other event producer
        # (chart.overlays.bar_events) converts via .tolist() for the same
        # reason - numpy bools break the indicators' integer arithmetic.
        event = BarClose(ts=ts, open=float(o[i]), high=float(h[i]), low=float(lo[i]),
                         close=float(c[i]), volume=float(v[i]),
                         delta=_optional(d[i]), vap=vap)
        row = registry.update(event)
        if row.get("session_bars") is None:
            continue
        if row["session_bars"] == 1:
            session_id = epoch
            session_label = split.label(epoch)

        if session_label == split.SEALED and not include_sealed:
            continue

        out = {
            "session_id": session_id,
            "session": row["session"],
            "split": session_label,
            "time": epoch,
            "open": float(o[i]), "high": float(h[i]), "low": float(lo[i]),
            "close": float(c[i]), "volume": float(v[i]), "delta": _optional(d[i]),
        }
        for name in _SCALARS:
            out[name] = row.get(name)
        out["n_hvn"] = len(row["session_hvn"]) if row.get("session_hvn") is not None else None
        out["n_lvn"] = len(row["session_lvn"]) if row.get("session_lvn") is not None else None
        rows.append(out)

        if progress is not None and i % 8192 == 0:
            progress(i, len(bars))

    frame = pd.DataFrame(rows)
    written: dict[str, object] = {}
    for label in ((split.EXPLORE, split.SEALED) if include_sealed else (split.EXPLORE,)):
        part = frame[frame["split"] == label]
        if include_sealed or label == split.EXPLORE:
            out_path = path(symbol, timeframe, label)
            part.to_parquet(out_path, index=False)
            written[label] = {"path": out_path, "rows": len(part),
                              "sessions": part["session_id"].nunique() if len(part) else 0}
            logger.info("Catalog %s: %s rows, %s sessions -> %s", label,
                        f"{len(part):,}", part["session_id"].nunique() if len(part) else 0,
                        out_path.name)
    return written


def _step_seconds(timeframe: str) -> int:
    units = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    return int(timeframe[:-1]) * units[timeframe[-1]]
