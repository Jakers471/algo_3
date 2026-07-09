"""Pin the port-ownership rules. Each of these encodes a bug we actually hit.

The pidfile used to be a single shared file. Running a second server on another
port overwrote it, and then `--stop --port X` read a stale record, terminated an
unrelated process, and left port X still bound. That is precisely the stacking
failure this module exists to prevent, so it is pinned here.
"""

from __future__ import annotations

import json
import os

import pytest

from src.chart import lifecycle


@pytest.fixture(autouse=True)
def pid_dir(tmp_path, monkeypatch):
    monkeypatch.setattr("src.config.chart.PID_DIR", tmp_path)
    return tmp_path


def test_each_port_gets_its_own_pidfile():
    assert lifecycle.pid_path(8765) != lifecycle.pid_path(8766)
    assert "8765" in lifecycle.pid_path(8765).name


def test_write_then_read_round_trips():
    lifecycle.write_pidfile("127.0.0.1", 9001)
    record = lifecycle.read_pidfile(9001)
    assert record["pid"] == os.getpid()
    assert record["port"] == 9001


def test_a_second_server_does_not_clobber_the_first(pid_dir):
    lifecycle.write_pidfile("127.0.0.1", 9001)
    first = lifecycle.read_pidfile(9001)
    lifecycle.write_pidfile("127.0.0.1", 9002)   # a second server, other port

    assert lifecycle.read_pidfile(9001) == first, "the first server's record survived"
    assert lifecycle.read_pidfile(9002)["port"] == 9002


def test_a_record_naming_another_port_is_refused(pid_dir):
    """A mismatched record must never authorize killing anything on this port."""
    lifecycle.pid_path(9001).write_text(json.dumps({"pid": 4242, "port": 8765}))
    assert lifecycle.read_pidfile(9001) is None


def test_missing_or_corrupt_pidfile_reads_as_none(pid_dir):
    assert lifecycle.read_pidfile(9999) is None
    lifecycle.pid_path(9998).write_text("not json")
    assert lifecycle.read_pidfile(9998) is None


def test_clear_is_per_port_and_idempotent(pid_dir):
    lifecycle.write_pidfile("127.0.0.1", 9001)
    lifecycle.write_pidfile("127.0.0.1", 9002)
    lifecycle.clear_pidfile(9001)

    assert lifecycle.read_pidfile(9001) is None
    assert lifecycle.read_pidfile(9002) is not None
    lifecycle.clear_pidfile(9001)   # no such file: must not raise


def test_process_alive_does_not_kill_the_process_it_asks_about():
    """os.kill(pid, 0) is TerminateProcess on Windows. This must never use it."""
    assert lifecycle._process_alive(os.getpid()) is True
    assert lifecycle._process_alive(os.getpid()) is True   # still here
    assert lifecycle._process_alive(-1) is False


def test_nothing_listening_means_the_port_is_free():
    assert lifecycle.port_in_use("127.0.0.1", 9) is False   # discard port, closed


# --- the probe must recognise our own server, even when it is broken ---------

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer


def _serve(status: int, signed: bool, body: bytes = b"{}"):
    """A one-shot HTTP server answering with (or without) our signature."""
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            if signed:
                self.send_header(lifecycle.SIGNATURE_HEADER, lifecycle.SIGNATURE)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def test_a_server_answering_200_is_recognised():
    server = _serve(200, signed=True)
    try:
        assert lifecycle.is_our_server("127.0.0.1", server.server_port)
    finally:
        server.shutdown()


def test_a_server_answering_500_is_still_ours():
    """urlopen raises HTTPError on 5xx, and HTTPError is a URLError.

    Swallowing it would rule that a server returning 500 is a stranger, and we
    would refuse to reclaim the port from the very server most in need of a
    restart. The signature is on the response either way.
    """
    server = _serve(500, signed=True, body=b'{"error":"internal"}')
    try:
        assert lifecycle.is_our_server("127.0.0.1", server.server_port)
    finally:
        server.shutdown()


def test_a_stranger_on_the_port_is_not_ours():
    server = _serve(200, signed=False)
    try:
        assert not lifecycle.is_our_server("127.0.0.1", server.server_port)
    finally:
        server.shutdown()


def test_nothing_listening_is_not_ours():
    assert not lifecycle.is_our_server("127.0.0.1", 1)
