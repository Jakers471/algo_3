"""Logging configuration: format, level, and destinations in one place.

One job: decide *how and where* logs are rendered. Every module gets its
logger with ``logging.getLogger(__name__)`` and decides *what* to log;
this module owns the look. Call ``setup_logging()`` once at startup.

Debug output is structured, neat, and elegant: an aligned timestamp and a
color-coded level tag carry the meaning that emoji would otherwise. No emoji.
"""

from __future__ import annotations

import logging

from src import console

# Level name -> color for the level tag.
_LEVEL_COLORS = {
    logging.DEBUG: console.GREY,
    logging.INFO: console.GREEN,
    logging.WARNING: console.YELLOW,
    logging.ERROR: console.RED,
    logging.CRITICAL: console.BOLD + console.RED,
}


class ColorFormatter(logging.Formatter):
    """Render ``[HH:MM:SS] LEVEL  message`` with a color-coded level tag."""

    def format(self, record: logging.LogRecord) -> str:
        ts = console.paint(self.formatTime(record, "%H:%M:%S"), console.DIM)
        color = _LEVEL_COLORS.get(record.levelno, "")
        level = console.paint(f"{record.levelname:<7}", color)
        return f"{console.paint('[', console.DIM)}{ts}{console.paint(']', console.DIM)} {level} {record.getMessage()}"


def setup_logging(level: int = logging.INFO) -> None:
    """Configure the root logger once, with colored console output."""
    console.enable_windows_ansi()

    root = logging.getLogger()
    root.setLevel(level)

    # Replace handlers so repeated calls don't stack duplicate output.
    for handler in list(root.handlers):
        root.removeHandler(handler)

    stream = logging.StreamHandler()
    stream.setFormatter(ColorFormatter())
    root.addHandler(stream)
