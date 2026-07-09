"""Pin how a snapshot row renders. No GUI needed - these are pure functions.

The rules that matter: a column appears because an indicator published a field
(so a new indicator needs no edit here), an absent value renders as absent and
never as zero, and colour carries direction the way it does on the chart.
"""

from __future__ import annotations

from src.config import table as cfg
from src.table import columns as cols


def snap(fields=None, **bar):
    base = {"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5, "volume": 10}
    base.update(bar)
    return {"time": 1_573_573_500, "bar": base, "fields": fields or {}}


# --- columns come from the session, not from a config -----------------------

def test_bar_columns_come_first_then_indicator_fields():
    keys = [k for k, _, _ in cols.columns_for(["session", "delta"])]
    assert keys == ["time", "open", "high", "low", "close", "volume", "session", "delta"]


def test_a_new_indicator_field_becomes_a_column_with_no_edit():
    keys = [k for k, _, _ in cols.columns_for(["absorption"])]
    assert keys[-1] == "absorption"


def test_numeric_fields_align_right_text_fields_left():
    by_key = {k: a for k, _, a in cols.columns_for(["session", "delta", "trades"])}
    assert by_key["delta"] == cols.RIGHT
    assert by_key["trades"] == cols.RIGHT
    assert by_key["session"] == cols.LEFT


# --- formatting -------------------------------------------------------------

def test_time_renders_in_utc():
    """The bars are UTC end to end; localising would make the clock lie."""
    assert cols.cell_text("time", snap()) == "2019-11-12 15:45:00"


def test_prices_and_volumes_are_grouped():
    assert cols.cell_text("close", snap(close=24619.0)) == "24,619.00"
    assert cols.cell_text("volume", snap(volume=1043)) == "1,043"


def test_signed_volume_shows_its_sign_but_zero_shows_none():
    assert cols.cell_text("delta", snap({"delta": 1204})) == "+1,204"
    assert cols.cell_text("delta", snap({"delta": -1358})) == "-1,358"
    assert cols.cell_text("delta", snap({"delta": 0})) == "0", "'+0' implies a direction"


def test_an_unavailable_value_renders_as_absent_never_as_zero():
    """A tick-only indicator fed bars publishes None. It must not read as flat."""
    assert cols.cell_text("delta", snap({"delta": None})) == "-"
    assert cols.cell_color("delta", snap({"delta": None})) == cfg.MUTED


def test_booleans_render_as_a_mark_or_nothing():
    assert cols.cell_text("session_new", snap({"session_new": True})) == "yes"
    assert cols.cell_text("session_new", snap({"session_new": False})) == ""


def test_an_unknown_field_type_still_renders():
    assert cols.cell_text("regime", snap({"regime": "consolidation"})) == "consolidation"


def test_an_indicators_timestamp_is_a_time_not_a_ten_digit_number():
    """swing_time, leg_from_time, bos_time - all epoch seconds, all unreadable raw."""
    assert cols.cell_text("swing_time", snap({"swing_time": 1573573500})) \
        == "2019-11-12 15:45:00"
    assert cols.cell_text("bos_time", snap({"bos_time": 1573573500})) \
        == "2019-11-12 15:45:00"
    assert cols.cell_text("swing_time", snap({"swing_time": None})) == "-"


def test_a_computed_float_is_not_printed_to_seventeen_digits():
    """retrace is a division. Nobody wants 1.4814814814814814."""
    assert cols.cell_text("retrace", snap({"retrace": 1.4814814814814814})) == "1.48"
    assert cols.cell_text("trigger", snap({"trigger": 27309.375})) == "27,309.38"
    assert cols.cell_text("extreme_high", snap({"extreme_high": 27594.25})) == "27,594.25"


def test_prices_and_ratios_line_up_on_the_right_words_on_the_left():
    by_key = {k: a for k, _, a in cols.columns_for(
        ["swing", "swing_price", "swing_time", "hunting", "retrace", "bos_level"])}
    assert by_key["swing_price"] == cols.RIGHT
    assert by_key["bos_level"] == cols.RIGHT
    assert by_key["retrace"] == cols.RIGHT
    assert by_key["swing_time"] == cols.LEFT, "a timestamp reads from the left"
    assert by_key["hunting"] == cols.LEFT
    assert by_key["swing"] == cols.LEFT


# --- colour -----------------------------------------------------------------

def test_close_is_coloured_by_the_candle_direction():
    assert cols.cell_color("close", snap(open=100.0, close=101.0)) == cfg.UP
    assert cols.cell_color("close", snap(open=100.0, close=99.0)) == cfg.DOWN


def test_delta_is_coloured_by_its_sign():
    assert cols.cell_color("delta", snap({"delta": 1204})) == cfg.UP
    assert cols.cell_color("delta", snap({"delta": -1358})) == cfg.DOWN
    assert cols.cell_color("delta", snap({"delta": 0})) == cfg.MUTED


def test_absorption_reads_as_a_green_close_beside_a_red_delta():
    """The contrast IS the signal: price rose while sellers were the aggressors."""
    row = snap({"delta": -1358}, open=100.0, close=101.0)
    assert cols.cell_color("close", row) == cfg.UP
    assert cols.cell_color("delta", row) == cfg.DOWN


def test_each_session_gets_its_own_accent_and_the_halt_is_muted():
    assert cols.cell_color("session", snap({"session": "NY"})) == cfg.SESSION_COLORS["NY"]
    assert cols.cell_color("session", snap({"session": "Asia"})) == cfg.SESSION_COLORS["Asia"]
    assert cols.cell_color("session", snap({"session": None})) == cfg.HALT_COLOR


# --- row-level marks --------------------------------------------------------

def test_a_session_open_is_flagged_for_the_row_rule():
    assert cols.row_is_session_open(snap({"session_new": True})) is True
    assert cols.row_is_session_open(snap({"session_new": False})) is False


def test_a_halt_row_is_detected_only_when_the_field_exists():
    assert cols.row_is_halt(snap({"session": None})) is True
    assert cols.row_is_halt(snap({"session": "NY"})) is False
    assert cols.row_is_halt(snap({})) is False, "no sessions indicator: not a halt"
