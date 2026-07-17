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


# --- every field is defined, and its unit is named ---------------------------

KNOWN_UNITS = {
    "price", "points", "contracts", "contracts, signed", "count",
    "x range_scale", "0..1", "-1..+1", "boolean", "payload",
    "epoch seconds, UTC", "ratio",
}


def test_every_published_field_is_defined():
    """A column nobody defined is a column nobody can read six months from now."""
    for entry in registry().provenance():
        missing = set(entry["fields"]) - set(entry["about"])
        assert not missing, f"{entry['id']} publishes {missing} with no definition"


def test_every_definition_names_a_unit_we_recognise():
    """`price`, `points` and `x range_scale` look identical in a table."""
    for entry in registry().provenance():
        for name, about in entry["about"].items():
            unit = about["unit"]
            enum = "|" in unit
            assert enum or unit in KNOWN_UNITS, f"{name}: unknown unit {unit!r}"
            assert about["means"].strip(), f"{name}: empty definition"


def test_the_bar_columns_are_defined_too():
    """The candle comes from the dataset, not an indicator, and still needs saying."""
    assert set(k for k, _, _ in cols.BAR_COLUMNS) == set(cols.BAR_ABOUT)


def test_the_ruler_is_the_only_thing_measured_in_points():
    """Everything measured IN range_scale is dimensionless. That is the whole point."""
    in_points = {name for e in registry().provenance()
                 for name, a in e["about"].items() if a["unit"] == "points"}
    assert in_points == {"range_scale"}


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


def test_both_documents_are_generated_from_the_same_contract():
    """FIELDS.md reads down one indicator; FIELDS_V2.md scans across all of them.

    Same registry, so the same fields, or one of them is quietly lying about what
    the row carries.
    """
    import re

    from src.cli.fields import contract, render_markdown, render_markdown_v2

    entries = contract()
    names = [n for e in entries for n in e["fields"]]
    for doc in (render_markdown(entries), render_markdown_v2(entries)):
        found = set(re.findall(r"^\|(?:[^|]*\|)?\s*`(\w+)`\s*\|", doc, re.M))
        assert set(names) <= found, sorted(set(names) - found)


def test_the_generated_table_has_one_row_per_field_and_five_cells_each():
    """A unit like `high | low | None` is pipe-separated, and a pipe is a cell wall.

    Unescaped, `swing` silently becomes five columns and every row below it reads
    as a different field. The document would look fine to the generator and be
    wrong to every reader.
    """
    from src.cli.fields import contract, render_markdown_v2

    entries = contract()
    doc = render_markdown_v2(entries)

    # Only the field table: the unit legend above it is two columns by design.
    body = doc.split("## Every field, defined", 1)[1].split("## What each", 1)[0]
    rows = [line for line in body.splitlines()
            if line.startswith("| ") and "| field |" not in line
            and set(line) - set("|- ")]

    expected = sum(len(e["fields"]) for e in entries) + 6   # + the bar's six
    assert len(rows) == expected, "one row per field, and the bar's six"

    for row in rows:
        assert len(_cells(row)) == 5, row[:80]


def _cells(row: str) -> list[str]:
    """Split on unescaped pipes only."""
    out, cur, escaped = [], "", False
    for char in row.strip()[1:-1]:
        if escaped:
            cur += char
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == "|":
            out.append(cur)
            cur = ""
        else:
            cur += char
    out.append(cur)
    return out
