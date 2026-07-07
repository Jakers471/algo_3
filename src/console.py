"""Terminal styling primitives: ANSI color codes and helpers.

One job: turn text into inline-colored terminal output (no emoji, ever).
Both the logging formatter and the CLI import from here so color codes
live in exactly one place.
"""

from __future__ import annotations

import os
import sys

# --- ANSI codes -----------------------------------------------------------
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"

GREY = "\033[90m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
WHITE = "\033[37m"


def enable_windows_ansi() -> None:
    """Enable ANSI escape processing on the Windows console (no-op elsewhere)."""
    if os.name != "nt":
        return
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        # ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004, on STD_OUTPUT_HANDLE (-11)
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except Exception:
        pass  # color is cosmetic; never let it break output


def supports_color() -> bool:
    """True when stdout is a real terminal that can render color."""
    return sys.stdout.isatty()


def paint(text: str, *styles: str) -> str:
    """Wrap ``text`` in the given styles, resetting afterwards.

    Falls back to plain text when the terminal has no color support.
    """
    if not styles or not supports_color():
        return text
    return f"{''.join(styles)}{text}{RESET}"
