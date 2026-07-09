"""What a snapshot row looks like as a table row. No GUI in here.

One job: turn a snapshot into cells - a label, a display string, an alignment
and a colour for each. Pure functions over dicts, so the formatting rules are
testable without opening a window.

Columns are NOT configured anywhere. The fixed ones describe the bar; the rest
come from whatever the replay session reports as its indicator fields. Add an
indicator and a column appears, with no edit to this file or to the window.

Colour carries meaning here exactly as it does on the chart: green and red for
direction and for the sign of signed volume, the session's own accent for its
name, muted grey for a value that does not exist. There are no emoji, ever.
"""

from __future__ import annotations

from datetime import datetime, timezone

from src.config import table as cfg

LEFT, RIGHT, CENTER = "left", "right", "center"

# The bar is always the first six columns; the rest are indicator fields.
BAR_COLUMNS = (
    ("time", "time", LEFT),
    ("open", "open", RIGHT),
    ("high", "high", RIGHT),
    ("low", "low", RIGHT),
    ("close", "close", RIGHT),
    ("volume", "volume", RIGHT),
)

# A field whose name we know how to render specially. Anything else falls back
# to a plain string, which is exactly what a brand-new indicator should get.
_SIGNED_FIELDS = {"delta"}
_VOLUME_FIELDS = {"volume", "buy_volume", "sell_volume", "trades"}


def columns_for(fields: list[str]) -> list[tuple[str, str, str]]:
    """(key, label, alignment) per column, bar first then indicator fields."""
    out = list(BAR_COLUMNS)
    for name in fields:
        align = RIGHT if (name in _SIGNED_FIELDS or name in _VOLUME_FIELDS) else LEFT
        out.append((name, name.replace("_", " "), align))
    return out


def fmt_time(epoch_seconds: int) -> str:
    """UTC, always. The bars are UTC end to end; localising would make it lie."""
    dt = datetime.fromtimestamp(int(epoch_seconds), tz=timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def fmt_price(value) -> str:
    return "-" if value is None else f"{float(value):,.2f}"


def fmt_int(value) -> str:
    return "-" if value is None else f"{int(value):,}"


def fmt_signed(value) -> str:
    """Signed volume. Zero is zero - a "+0" implies a direction it does not have."""
    if value is None:
        return "-"
    number = int(value)
    return "0" if number == 0 else f"{number:+,}"


def cell_text(key: str, snapshot: dict) -> str:
    """The display string for one cell of one snapshot."""
    if key == "time":
        return fmt_time(snapshot["time"])
    if key in ("open", "high", "low", "close"):
        return fmt_price(snapshot["bar"].get(key))
    if key == "volume":
        return fmt_int(snapshot["bar"].get("volume"))

    value = snapshot.get("fields", {}).get(key)
    if value is None:
        # A field that is absent, not zero. A tick-only indicator fed bars says
        # so here rather than showing a fabricated number.
        return "-"
    if isinstance(value, bool):
        return "yes" if value else ""
    if key in _SIGNED_FIELDS:
        return fmt_signed(value)
    if key in _VOLUME_FIELDS:
        return fmt_int(value)
    return str(value)


def cell_color(key: str, snapshot: dict) -> str | None:
    """The foreground colour for one cell, or None for the default text colour."""
    fields = snapshot.get("fields", {})

    if key == "close":
        bar = snapshot["bar"]
        if bar.get("open") is None or bar.get("close") is None:
            return None
        return cfg.UP if bar["close"] >= bar["open"] else cfg.DOWN

    if key in _SIGNED_FIELDS:
        value = fields.get(key)
        if value is None:
            return cfg.MUTED
        if value == 0:
            return cfg.MUTED
        return cfg.UP if value > 0 else cfg.DOWN

    if key == "session":
        name = fields.get(key)
        return cfg.SESSION_COLORS.get(name, cfg.HALT_COLOR) if name else cfg.HALT_COLOR

    if key == "session_new":
        return cfg.ACCENT if fields.get(key) else None

    if fields.get(key) is None and key in fields:
        return cfg.MUTED

    return None


def row_is_session_open(snapshot: dict) -> bool:
    """A session boundary: worth a rule above the row, as on the chart."""
    return bool(snapshot.get("fields", {}).get("session_new"))


def row_is_halt(snapshot: dict) -> bool:
    """No session: the daily CME maintenance halt. Dim the whole row."""
    fields = snapshot.get("fields", {})
    return "session" in fields and fields["session"] is None
