"""Read SESSION_SPLIT.json: which sessions may be looked at, and which are sealed.

One job: load the committed seal once and answer, for a session's start time,
"explore" or "sealed". Every piece of analysis machinery routes through this
one reader - the catalog builder, the percentile-table builder, and whatever
evaluates a frozen rule later - so the boundary is enforced in exactly one
place and cannot drift between callers.

Two artifacts, one boundary, checked against each other. The DECLARATION is
``config/session_history.py``'s SEALED_FROM - a round date near the two-thirds
mark, deliberately not tuned. The RECEIPT is ``SESSION_SPLIT.json`` at the
repo root - frozen and committed like DATA_AUDIT.json, written once by
scratch/analysis/seal_split.py (guarded against re-runs), recording exactly
which sessions that declaration seals: counts, spans, the rule. ``load()``
refuses to answer if the two disagree, so neither can drift quietly.

The most recent third of all London/NY sessions is SEALED - not plotted, not
eyeballed, not "just checked" - until a rule is frozen and gets its one
honest evaluation. Split by TIME, not at random, because volatility clusters:
a random split leaks, since a day in explore informs the day beside it in
test. See the JSON's own `rule` and `why_time_split` fields.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from src.config import session_history as cfg

_ROOT = Path(__file__).resolve().parents[2]
SPLIT_FILE = _ROOT / "SESSION_SPLIT.json"

_CACHE: dict | None = None

EXPLORE, SEALED = "explore", "sealed"


class NotSealed(FileNotFoundError):
    """SESSION_SPLIT.json does not exist. Run: python -m scratch.analysis.seal_split"""


class SealDrift(RuntimeError):
    """The receipt and the declaration disagree. Neither may be trusted until
    a human decides which one moved, and why - this is exactly the quiet
    un-sealing the two-artifact design exists to catch."""


def load() -> dict:
    global _CACHE
    if _CACHE is None:
        if not SPLIT_FILE.exists():
            raise NotSealed(
                "no SESSION_SPLIT.json - the vault has not been sealed; "
                "run: python -m scratch.analysis.seal_split")
        data = json.loads(SPLIT_FILE.read_text(encoding="utf-8"))
        declared = int(datetime(cfg.SEALED_FROM.year, cfg.SEALED_FROM.month,
                                cfg.SEALED_FROM.day, tzinfo=timezone.utc).timestamp())
        if int(data["cutoff_epoch"]) != declared:
            raise SealDrift(
                f"SESSION_SPLIT.json cutoff {data['cutoff_epoch']} != "
                f"config SEALED_FROM {cfg.SEALED_FROM.isoformat()} ({declared}). "
                "One of them moved. Decide which, say why in a commit, and "
                "re-run scratch/analysis/seal_split.py --force to re-freeze.")
        _CACHE = data
    return _CACHE


def cutoff() -> int:
    """The seal, in epoch seconds. At or after it, a session is sealed."""
    return int(load()["cutoff_epoch"])


def label(session_start_epoch: int) -> str:
    """"explore" or "sealed", by the session's FIRST bar's close time.

    Keyed on the start so no session straddles the boundary - and every
    future session, as new data lands, is automatically sealed too.
    """
    return SEALED if session_start_epoch >= cutoff() else EXPLORE


def is_sealed(session_start_epoch: int) -> bool:
    return label(session_start_epoch) == SEALED
