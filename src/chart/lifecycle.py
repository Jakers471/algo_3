"""One chart server at a time, and prove it stopped.

One job: guarantee the port has exactly one owner. Starting reclaims the port
from a previous server; stopping is confirmed by watching the port go dead,
not by assuming a signal was honored.

Why this is a real problem and not a nicety: `http.server.HTTPServer` sets
`allow_reuse_address = True`. On Linux that only bypasses TIME_WAIT, but on
Windows SO_REUSEADDR lets a *second* process bind a port that is already
actively listening - so a re-launch silently stacks another server behind the
first instead of failing. Requests then land on whichever socket the kernel
picks. That is why servers pile up.

The fix is two-sided: refuse to share the port (SO_EXCLUSIVEADDRUSE on Windows),
and reclaim it deliberately on startup.

Identification is by pidfile AND a signature header, never by pid alone: a pid
is reused by the OS, and killing a stranger because it inherited a dead
server's number would be unforgivable. We kill a process only when the pidfile
names it and the port answers as one of ours.

Knows nothing about bars or HTTP routes - only about sockets and processes.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import signal
import socket
import sys
import time
import urllib.error
import urllib.request

from src.config import chart as chart_cfg

logger = logging.getLogger(__name__)

# Sent on every response; how we recognize our own server on a port.
SIGNATURE_HEADER = "X-Chart-Server"
SIGNATURE = "algo3-chart"


class PortBusy(RuntimeError):
    """The port is held by a process that is not one of our chart servers."""


# --- port probing -----------------------------------------------------------

def port_in_use(host: str, port: int, timeout: float = 0.3) -> bool:
    """True if something accepts a TCP connection on host:port right now."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        return sock.connect_ex((host, port)) == 0


def is_our_server(host: str, port: int, timeout: float = 0.6) -> bool:
    """True if the listener on this port identifies itself as our chart server."""
    url = f"http://{host}:{port}/api/config"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return response.headers.get(SIGNATURE_HEADER) == SIGNATURE
    except (urllib.error.URLError, OSError, TimeoutError):
        return False


def wait_until_free(host: str, port: int, timeout: float) -> bool:
    """Poll until nothing is listening. The confirmation that a stop worked."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not port_in_use(host, port):
            return True
        time.sleep(0.1)
    return not port_in_use(host, port)


# --- pidfile ----------------------------------------------------------------

def write_pidfile(host: str, port: int) -> None:
    chart_cfg.PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    chart_cfg.PID_FILE.write_text(json.dumps({
        "pid": os.getpid(), "host": host, "port": port, "started": time.time(),
    }))


def read_pidfile() -> dict | None:
    try:
        return json.loads(chart_cfg.PID_FILE.read_text())
    except (OSError, ValueError):
        return None


def clear_pidfile() -> None:
    with contextlib.suppress(OSError):
        chart_cfg.PID_FILE.unlink()


if sys.platform == "win32":
    import ctypes

    _KERNEL32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _SYNCHRONIZE = 0x00100000
    _WAIT_TIMEOUT = 0x00000102  # still running; anything else means it ended

    def _process_alive(pid: int) -> bool:
        """Is this pid a live process?

        NOT `os.kill(pid, 0)`. On POSIX signal 0 is a pure existence probe, but
        CPython implements os.kill on Windows as TerminateProcess - so the
        "probe" would kill the very process it is asking about, then raise
        WinError 87 forever after. We open a handle and check whether the
        process object is still unsignaled instead.
        """
        if pid <= 0:
            return False
        handle = _KERNEL32.OpenProcess(_SYNCHRONIZE, False, pid)
        if not handle:
            return False  # no such process (or not ours to see)
        try:
            return _KERNEL32.WaitForSingleObject(handle, 0) == _WAIT_TIMEOUT
        finally:
            _KERNEL32.CloseHandle(handle)

else:
    def _process_alive(pid: int) -> bool:
        """Is this pid a live process? (signal 0 delivers nothing on POSIX)."""
        if pid <= 0:
            return False
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True  # exists, owned by someone else
        return True


def _terminate(pid: int, timeout: float) -> bool:
    """Ask a process to exit, then insist. True if it is gone.

    On Windows os.kill() is TerminateProcess: immediate, and the target's
    signal handler never runs. That is why callers confirm the *port* is free
    rather than trusting a graceful shutdown to have happened.
    """
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return True
    except OSError as exc:
        # A dead pid on Windows surfaces here as WinError 87, not ProcessLookupError.
        if not _process_alive(pid):
            return True
        logger.warning("Could not signal pid %d: %s", pid, exc)
        return False

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _process_alive(pid):
            return True
        time.sleep(0.1)

    logger.warning("pid %d ignored SIGTERM; forcing", pid)
    with contextlib.suppress(OSError):
        # No SIGKILL on Windows - but there os.kill() already terminated it.
        os.kill(pid, getattr(signal, "SIGKILL", signal.SIGTERM))
    return not _process_alive(pid)


# --- the two public moves ---------------------------------------------------

def stop_running(host: str, port: int) -> bool:
    """Stop the chart server on this port, if one of ours is there.

    Returns True if the port ended up free. Raises PortBusy if a foreign
    process holds it - we will not kill something we did not start.
    """
    if not port_in_use(host, port):
        clear_pidfile()
        return True

    if not is_our_server(host, port):
        raise PortBusy(
            f"Port {port} is held by a process that is not a chart server. "
            f"Stop it, or start the chart on another port: --port <n>"
        )

    record = read_pidfile()
    pid = record.get("pid") if record else None
    if not pid or not _process_alive(pid):
        raise PortBusy(
            f"A chart server is listening on {port} but no pidfile names it "
            f"({chart_cfg.PID_FILE}). Close that terminal, or use --port <n>."
        )

    logger.info("Reclaiming port %d from chart server pid %d", port, pid)
    _terminate(pid, chart_cfg.SHUTDOWN_TIMEOUT)

    if not wait_until_free(host, port, chart_cfg.SHUTDOWN_TIMEOUT):
        raise PortBusy(f"Port {port} still in use after stopping pid {pid}")

    clear_pidfile()
    logger.info("Port %d released - confirmed closed", port)
    return True


def install_signal_handlers(shutdown) -> None:
    """Run `shutdown` on Ctrl-C and on SIGTERM (so a reclaim is graceful)."""
    def handler(signum, _frame):
        logger.info("Received %s - shutting down", signal.Signals(signum).name)
        shutdown()

    signal.signal(signal.SIGINT, handler)
    if sys.platform != "win32":
        signal.signal(signal.SIGTERM, handler)
    else:
        # Windows delivers SIGTERM from os.kill as SIGBREAK-ish; register what exists.
        with contextlib.suppress(ValueError, AttributeError, OSError):
            signal.signal(signal.SIGTERM, handler)
