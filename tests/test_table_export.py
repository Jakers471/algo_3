"""Pins the pasted format: raw keys, real context, nothing invented.

The export exists to be read by someone who was never at the screen, so the
things that matter are the ones the screen supplies for free and text does not -
which market, which scale, which field is which.
"""

from __future__ import annotations

from src.table import columns as cols
from src.table import export

GROUPS = [
    {"id": "session_stats",
     "fields": ["session_range", "session_efficiency", "session_delta_recent"]},
    {"id": "sessions", "fields": ["session"]},
]

SESSION = {"id": "abc123", "symbol": "NQT", "timeframe": "5m"}


def _snapshot(**fields):
    row = {"time": 1_700_000_000,
           "bar": {"open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5, "volume": 10},
           "fields": {"session_range": None, "session_efficiency": None,
                      "session_delta_recent": None, "session": "NY"}}
    row["fields"].update(fields)
    return row


def test_headers_are_raw_field_keys_not_the_screen_labels():
    """The header shows `efficiency` under a `session_stats` heading; text has no
    heading, and `session_efficiency` is what FIELDS.md defines."""
    columns = cols.columns_for(GROUPS, only=["session_stats"])
    out = export.as_markdown(columns, [_snapshot()], SESSION)
    header = [line for line in out.splitlines() if line.startswith("| time")][0]

    assert "session_efficiency" in header
    assert "session_delta_recent" in header
    # The screen's shortened label must not be what lands in the paste.
    assert "| efficiency |" not in header


def test_the_context_line_says_which_market_and_which_blocks():
    columns = cols.columns_for(GROUPS, only=["session_stats"])
    out = export.as_markdown(columns, [_snapshot(), _snapshot()], SESSION)
    first = out.splitlines()[0]

    assert "NQT 5m" in first
    assert "session abc123" in first
    assert "blocks: bar, session_stats" in first
    assert "2 row(s)" in first


def test_an_absent_field_stays_absent():
    """`-` is a field that does not exist. A 0 here would be a fabricated fact."""
    columns = cols.columns_for(GROUPS, only=["session_stats"])
    out = export.as_markdown(columns, [_snapshot(session_delta_recent=None)], SESSION)
    body = out.splitlines()[-1]

    assert "| - |" in body
    assert "| 0 |" not in body


def test_the_filter_reaches_the_paste():
    """Copying a filtered table must not quietly paste the columns it hid."""
    columns = cols.columns_for(GROUPS, only=["session_stats"])
    out = export.as_markdown(columns, [_snapshot()], SESSION)

    assert "session_efficiency" in out
    assert "sessions" not in out.splitlines()[2]   # the header row


def test_alignment_survives_the_trip():
    columns = cols.columns_for(GROUPS, only=["session_stats"])
    out = export.as_markdown(columns, [_snapshot()], SESSION)
    rule = [line for line in out.splitlines() if "---" in line][0]

    assert "---:" in rule      # numbers line up right
    assert ":---" in rule      # time reads from the left


def test_a_pipe_in_a_cell_cannot_break_the_table():
    columns = cols.columns_for(GROUPS, only=["sessions"])
    out = export.as_markdown(columns, [_snapshot(session="N|Y")], SESSION)
    body = out.splitlines()[-1]

    assert "N\\|Y" in body
    # The escaped pipe is still a `|` character; only the unescaped ones divide
    # columns, and there must be exactly one more of those than there are columns.
    assert body.count("|") - body.count("\\|") == len(columns) + 1


def test_nothing_selected_copies_nothing():
    """Empty in, empty out - never a header with no rows under it."""
    columns = cols.columns_for(GROUPS)
    assert export.as_markdown(columns, [], SESSION) == ""
    assert export.as_markdown([], [_snapshot()], SESSION) == ""
