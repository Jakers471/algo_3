"""A minimal ANSI progress bar for long loops - terminal-native, no emoji.

One job: render an in-place ``[####----] 42.0% (n/total) 1.2s`` bar to stderr.
Throttled so frequent updates stay cheap. Used by CLI doors over slow loops.
"""

from __future__ import annotations

import sys
import time

from src.core import console


class ProgressBar:
    def __init__(self, total: int, label: str = "", width: int = 32, min_interval: float = 0.1) -> None:
        self.total = max(int(total), 1)
        self.label = label
        self.width = width
        self.min_interval = min_interval
        self._n = 0
        self._last = 0.0
        self._start = time.time()

    def update(self, n: int) -> None:
        self._n = n
        now = time.time()
        if n < self.total and (now - self._last) < self.min_interval:
            return
        self._last = now
        self._render()

    def _render(self) -> None:
        frac = min(max(self._n / self.total, 0.0), 1.0)
        filled = int(self.width * frac)
        bar = "#" * filled + "-" * (self.width - filled)
        elapsed = time.time() - self._start
        line = f"  {self.label} [{bar}] {frac * 100:5.1f}%  ({self._n:,}/{self.total:,})  {elapsed:4.1f}s"
        sys.stderr.write("\r" + console.paint(line, console.CYAN))
        sys.stderr.flush()

    def close(self) -> None:
        self._n = self.total
        self._render()
        sys.stderr.write("\n")
        sys.stderr.flush()
