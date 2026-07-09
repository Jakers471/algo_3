"""Pins the field contract: a column, the indicator that filled it, and its files.

A snapshot row is a flat wall of names. The contract says which file computed
each one and which dial moves it, and it is DERIVED from the indicator classes
rather than written beside them - so it cannot drift.

The last test is the one that matters: FIELDS.md must equal what the code
generates right now. Add a field and forget to regenerate, and the suite says so.
"""

from __future__ import annotations

from pathlib import Path

from src.chart import overlays
from src.cli import fields as door
from src.config import table as table_cfg
from src.table import columns as cols

ROOT = Path(__file__).resolve().parents[1]


def registry():
    return overlays.build_registry(profile_mode="on")


# --- provenance --------------------------------------------------------------

def test_every_field_is_published_by_exactly_one_indicator():
    """Two indicators publishing the same name would silently overwrite a row."""
    reg = registry()
    names = [name for entry in reg.provenance() for name in entry["fields"]]
    assert len(names) == len(set(names))
    assert set(names) == set(reg.field_names())


def test_each_indicator_names_a_source_file_that_exists():
    for entry in registry().provenance():
        assert (ROOT / entry["source"]).is_file(), entry["source"]


def test_a_config_file_is_named_when_there_is_one_and_None_when_there_is_not():
    by_id = {e["id"]: e for e in registry().provenance()}
    assert by_id["swing"]["config"] == "src/config/indicators/swing.py"
    assert (ROOT / by_id["swing"]["config"]).is_file()
    # base.py's helper must report absence rather than invent a path.
    for entry in registry().provenance():
        if entry["config"] is not None:
            assert (ROOT / entry["config"]).is_file()


def test_dependencies_are_listed_and_come_earlier():
    """The contract is printed in run order; a dependency is always above."""
    entries = registry().provenance()
    seen: set[str] = set()
    for entry in entries:
        assert set(entry["depends"]) <= seen, f"{entry['id']} runs before what it reads"
        seen.add(entry["id"])


def test_field_source_maps_a_column_back_to_its_indicator():
    source = registry().field_source()
    assert source["retrace"] == "swing"
    assert source["delta_at_poc"] == "profile"
    assert source["bos"] == "breaks"


# --- the table's colours are part of the same contract ------------------------

def test_every_running_indicator_has_a_colour():
    """A column whose hue is a fallback tells the reader nothing about its origin."""
    groups = {e["id"] for e in registry().provenance()} | {"bar"}
    missing = groups - set(table_cfg.GROUP_COLORS)
    assert not missing, f"no colour for {missing}"


def test_the_colour_rides_the_header_never_a_cell():
    """A cell's colour already means up, down, or absent. Two meanings is one too many."""
    snapshot = {"time": 0, "bar": {}, "fields": {"retrace": 1.0}}
    assert cols.cell_color("retrace", snapshot) is None


# --- the generated doc must not drift ----------------------------------------

def test_fields_md_matches_what_the_code_generates():
    """Add a field, forget to regenerate, and this fails.

    Run: python -m src.cli.fields --write
    """
    current = (ROOT / "FIELDS.md").read_text(encoding="utf-8")
    assert current == door.render_markdown(door.contract()), (
        "FIELDS.md is stale - run: python -m src.cli.fields --write")
