"""Restart the chart server when its Python changes. Development only.

One job: watch the source tree and say when something changed.

Static assets need none of this - the server reads HTML/CSS/JS off disk on every
request and sends ``Cache-Control: no-cache``, so Ctrl-R already picks them up.
Python is different: a module is imported once, and an edited indicator or config
value keeps serving the old code until the process restarts. This makes the
restart automatic instead of manual.

It watches, it does not restart: it sets an Event and lets ``server.serve`` shut
down cleanly, confirm the port is free, and let the CLI re-exec. Killing the
process from a watcher thread would leave the socket in limbo, which is exactly
the stacked-server problem lifecycle.py exists to prevent.

Polling mtimes, not filesystem events: no dependency, a few hundred files, and a
600ms sweep costs well under a millisecond.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

POLL_SECONDS = 0.6

# Only Python needs a restart. Static files are re-read per request.
WATCH_SUFFIXES = (".py",)


def _signature(roots: list[Path]) -> dict[str, float]:
    """Path -> mtime for every watched file under the roots."""
    stamps: dict[str, float] = {}
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.suffix in WATCH_SUFFIXES and "__pycache__" not in path.parts:
                try:
                    stamps[str(path)] = path.stat().st_mtime
                except OSError:
                    pass  # deleted mid-sweep; the next sweep sees it gone
    return stamps


def _describe(before: dict[str, float], after: dict[str, float]) -> str:
    changed = [p for p, m in after.items() if before.get(p) != m]
    added = [p for p in after if p not in before]
    removed = [p for p in before if p not in after]
    first = (changed or added or removed or ["?"])[0]
    return Path(first).name


def watch(roots: list[Path], changed: threading.Event,
          stop: threading.Event) -> threading.Thread:
    """Poll ``roots``; set ``changed`` and ``stop`` on the first modification.

    Returns the daemon thread, already started. ``stop`` is the server's own stop
    event, so tripping it unwinds the normal, confirmed shutdown path.
    """
    baseline = _signature(roots)

    def loop() -> None:
        nonlocal baseline
        while not stop.wait(POLL_SECONDS):
            current = _signature(roots)
            if current != baseline:
                logger.info("Reload: %s changed - restarting", _describe(baseline, current))
                baseline = current
                changed.set()
                stop.set()
                return

    thread = threading.Thread(target=loop, name="chart-autoreload", daemon=True)
    thread.start()
    logger.info("Autoreload: watching %d Python files", len(baseline))
    return thread
