"""Choose a session to look at - at random, and never from the vault.

One job: list the explore-side London/NY sessions in a dataset, and pick one.

**Random is not a convenience here, it is the point.** Left to choose, a person
picks the sessions they remember - the violent ones, the ones that made a good
story, the ones that already argue for whatever they currently believe. That is
a biased sample drawn by hand, and every conclusion from it inherits the bias
without recording it anywhere. Drawing uniformly from the explore set is the
cheapest correction there is, and it happens to also be less typing than finding
a date by eye.

It refuses to return a sealed session, so the one way to eyeball the vault is to
go around this module deliberately rather than to forget. That asymmetry is the
whole design: the honest path is the easy one.

Segmentation comes from ``sessions.session_runs`` - the same batch counterpart
to the live state machine that ``build.py`` and ``catalog.py`` walk, never a
second opinion about where a session starts.
"""

from __future__ import annotations

import random

from src.config.indicators import session_stats as ss_cfg
from src.data.loader import load_raw
from src.indicators.sessions import session_runs
from src.session_history import split


def explore_sessions(symbol: str, timeframe: str,
                     name: str | None = None) -> list[tuple[str, int]]:
    """``(session name, start epoch seconds)`` for every explore session.

    ``name`` narrows to one of ``TRACKED_SESSIONS`` ("NY", "London").
    """
    tracked = ((name,) if name else ss_cfg.TRACKED_SESSIONS)
    # volume too: session_runs' docstring says open/high/low/close, but it
    # builds a real BarClose per row and that reads row.volume.
    bars = load_raw(symbol, timeframe)[["open", "high", "low", "close", "volume"]]
    out = []
    for session_name, idx in session_runs(bars, tuple(tracked)):
        start = int(bars.index[idx[0]].timestamp())
        if not split.is_sealed(start):
            out.append((session_name, start))
    return out


def random_explore(symbol: str, timeframe: str, name: str | None = None,
                   seed: int | None = None) -> tuple[str, int]:
    """One explore session, uniformly at random. ``seed`` makes it repeatable.

    Raises ``LookupError`` rather than returning nothing: an empty explore set
    means the seal or the dataset is wrong, and a caller silently looking at no
    session is worse than one that stops.
    """
    sessions = explore_sessions(symbol, timeframe, name)
    if not sessions:
        raise LookupError(
            f"no explore sessions for {symbol} {timeframe}"
            + (f" named {name}" if name else "")
            + " - check SESSION_SPLIT.json against the dataset's span")
    return random.Random(seed).choice(sessions)
