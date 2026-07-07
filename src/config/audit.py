"""Front door to DATA_AUDIT.json — the data's own rules, read once.

One job: load the audit artifact and expose its fixed facts (contract specs,
handling flags, data end) so other config sections read them from a single
source of truth instead of re-typing the numbers. Re-running the audit
regenerates the file; config follows automatically.
"""

from __future__ import annotations

import json
from pathlib import Path

# DATA_AUDIT.json lives at the repo root: src/config/audit.py -> parents[2].
_AUDIT_PATH = Path(__file__).resolve().parents[2] / "DATA_AUDIT.json"


def _load() -> dict:
    with open(_AUDIT_PATH, encoding="utf-8") as fh:
        return json.load(fh)


RAW = _load()

VERDICT: str | None = RAW.get("verdict")
CONTRACT_SPECS: dict = RAW.get("contract_specs", {})
# handling flags keyed by id, e.g. HANDLING["back_adjustment"]["severity"].
HANDLING: dict = {h["id"]: h for h in RAW.get("handling", [])}


def _data_end() -> str | None:
    """Latest bar timestamp across all audited files (the stale-data boundary)."""
    ends = [f["end"] for f in RAW.get("files", []) if f.get("end")]
    return max(ends) if ends else None


DATA_END: str | None = _data_end()
