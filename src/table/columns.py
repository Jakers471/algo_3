"""What a snapshot row looks like as a table row. No GUI in here.

One job: turn a snapshot into cells - a label, a display string, an alignment
and a colour for each. Pure functions over dicts, so the formatting rules are
testable without opening a window.

Columns are NOT configured anywhere. The fixed ones describe the bar; the rest
come from whatever the replay session reports as its indicator fields, GROUPED by
the indicator that published them. Add an indicator and a group appears, with no
edit to this file or to the window.

**The row is not the view.** A snapshot carries everything a renderer needs,
which is more than a reader wants. There is only one kind of object in the
structure layer - a swing point, a price and a time - and six fields point at
one: `swing_price`, `leg_from_price`, `leg_to_price`, `bos_level`,
`extreme_high`, `extreme_low`. Shown as six columns they read as six facts. They
are not.

So this module distinguishes three things:

  a FACT      the state of the market, shown by default
  a COMPOSITE an event and the price it happened at, collapsed into one cell
              ("high 27,642.50" rather than three columns)
  a DETAIL    the timestamps and endpoints a drawing needs and a reader does not

Details are hidden unless asked for. Nothing is dropped from the row - the chart
still draws from every one of them, and the brain will still read them.

Colour carries meaning here exactly as it does on the chart: green and red for
direction and for the sign of signed volume, the session's own accent for its
name, muted grey for a value that does not exist. There are no emoji, ever.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import NamedTuple

from src.config import table as cfg

LEFT, RIGHT, CENTER = "left", "right", "center"

BAR_GROUP = "bar"


class Column(NamedTuple):
    key: str
    label: str
    align: str
    group: str
    first_in_group: bool


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

# Named prices that do not end in _price: they are levels on the chart's scale.
_PRICE_FIELDS = {"extreme_high", "extreme_low", "trigger", "range_scale"}


def is_time_field(name: str) -> bool:
    """A market timestamp, in epoch seconds. Rendered as UTC, never as a number.

    Every indicator that names a bar - the swing that made a high, the level a
    break took out - publishes its epoch. Printed raw, `1782917100` reads as a
    price with ten digits, and the column is unusable.
    """
    return name.endswith("_time")


def is_price_field(name: str) -> bool:
    return name in _PRICE_FIELDS or name.endswith(("_price", "_level"))


def _right_aligned(name: str) -> bool:
    """Digits line up on the right; words and timestamps read from the left."""
    return (name in _SIGNED_FIELDS or name in _VOLUME_FIELDS
            or is_price_field(name) or name == "retrace")


# An event and the price it happened at, shown in one cell instead of three.
# The second field is folded into the first; both stay in the row.
COMPOSITES = {
    "swing": "swing_price",     # "high 27,642.50"
    "bos": "bos_level",         # "up 27,642.50"
}

# Values a drawing needs and a reader does not.
_DERIVED = {"trigger"}          # = extreme -/+ RETRACE * range_scale


def is_detail(name: str) -> bool:
    """Hidden unless asked for: scaffolding, not a fact about the market."""
    if is_time_field(name):
        return True                      # which bar, not what happened
    if name in COMPOSITES.values():
        return True                      # folded into its event's cell
    if name in _DERIVED:
        return True                      # arithmetic on columns already shown
    if name == "leg" or name.startswith("leg_"):
        # `legs` joins two swings with a line. It knows nothing the swings do
        # not; it is a drawing, and five columns of one.
        return True
    return False


def columns_for(groups, *, show_all: bool = False) -> list[Column]:
    """Bar columns, then one block per indicator, in dependency order.

    ``groups`` is what the session publishes: ``[{"id", "fields"}, ...]``. A bare
    list of field names is accepted too, and lands in a single unnamed group.
    """
    if groups and isinstance(groups[0], str):
        groups = [{"id": "fields", "fields": list(groups)}]

    out = [Column(k, label, align, BAR_GROUP, i == 0)
           for i, (k, label, align) in enumerate(BAR_COLUMNS)]

    for group in groups or []:
        shown = [f for f in group["fields"] if show_all or not is_detail(f)]
        for i, name in enumerate(shown):
            out.append(Column(name, name.replace("_", " "),
                              RIGHT if _right_aligned(name) else LEFT,
                              group["id"], i == 0))
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

    fields = snapshot.get("fields", {})
    value = fields.get(key)
    if value is None:
        # A field that is absent, not zero. A tick-only indicator fed bars says
        # so here rather than showing a fabricated number.
        return "-"

    if key in COMPOSITES:
        # "high" alone is half a fact. The price it happened at is the other
        # half, and it is sitting in the next column doing nothing else.
        price = fields.get(COMPOSITES[key])
        return f"{value} {fmt_price(price)}" if price is not None else str(value)

    if isinstance(value, bool):
        return "yes" if value else ""
    if is_time_field(key):
        return fmt_time(value)
    if key in _SIGNED_FIELDS:
        return fmt_signed(value)
    if key in _VOLUME_FIELDS:
        return fmt_int(value)
    if is_price_field(key) or isinstance(value, float):
        # A float printed by repr carries all seventeen digits it was computed
        # with. `retrace` is a division; nobody wants 1.4814814814814814.
        return fmt_price(value)
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

    if key == "absorption":
        return cfg.ABSORPTION if fields.get(key) else None

    if key == "absorption_side":
        side = fields.get(key)
        if side == "buy":
            return cfg.UP        # buyers absorbed the sellers
        if side == "sell":
            return cfg.DOWN      # sellers absorbed the buyers
        return None

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


def row_is_absorption(snapshot: dict) -> bool:
    """Price closed against its own order flow. The row worth finding."""
    return bool(snapshot.get("fields", {}).get("absorption"))
