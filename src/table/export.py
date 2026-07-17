"""Turn selected rows into text you can paste somewhere else. No GUI in here.

One job: a run of snapshots as a markdown table. A row that looks wrong on screen
is worth showing to someone - a chat, an issue, a note - and a screenshot of it
cannot be read back, searched, or diffed. Pure functions over the same `Column`
list and snapshot dicts the model already holds, so the format is testable
without opening a window.

Three choices worth naming, because each one is the opposite of what the screen
does and each is right for a reader who was never at the screen:

- RAW FIELD KEYS, not the header's labels. The header prints the group above the
  field, so it can afford to show `efficiency` under a `session_stats` heading.
  Pasted text has no second header line, and `session_efficiency` is what
  FIELDS.md defines and what a reader can look up.
- THE CONTEXT LINE. Which symbol, which rung, which session. A wall of ratios
  means nothing without it, and the reader cannot glance at the title bar.
- DETAIL COLUMNS COME IF THEY ARE SHOWN. The export copies the columns the table
  is currently showing - filter and Details toggle included - because what you
  are looking at is what you meant to send.
"""

from __future__ import annotations

from src.table import columns as cols


def _blocks(columns) -> list[str]:
    """Each indicator block, once, in the order it appears."""
    seen = []
    for column in columns:
        if column.group not in seen:
            seen.append(column.group)
    return seen


def context_line(columns, rows, session: dict) -> str:
    """Which market, which scale, which blocks. The reader was not at the screen."""
    symbol = session.get("symbol", "?")
    timeframe = session.get("timeframe", "?")
    return (f"{symbol} {timeframe}  |  session {session.get('id', '?')}  |  "
            f"blocks: {', '.join(_blocks(columns))}  |  {len(rows)} row(s)")


def _escape(text: str) -> str:
    """A pipe in a cell would end the column early."""
    return text.replace("|", "\\|")


def as_markdown(columns, rows, session: dict | None = None) -> str:
    """A markdown table of these rows, in these columns. Empty in, empty out.

    The alignment row carries each column's own alignment, so numbers still line
    up right and words still read from the left wherever this lands.
    """
    if not columns or not rows:
        return ""

    header = [_escape(column.key) for column in columns]
    rule = ["---:" if column.align == cols.RIGHT else ":---" for column in columns]

    lines = []
    if session:
        lines.append(context_line(columns, rows, session))
        lines.append("")
    lines.append("| " + " | ".join(header) + " |")
    lines.append("| " + " | ".join(rule) + " |")
    for snapshot in rows:
        cells = [_escape(cols.cell_text(column.key, snapshot)) for column in columns]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)
