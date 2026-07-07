"""Audit area: read the data-truth facts proven in DATA_AUDIT.json.

``from src.audit import reader`` exposes the audit's fixed facts (contract
specs, handling flags, data end) as the single source of truth other code
reads instead of re-typing the numbers.
"""
