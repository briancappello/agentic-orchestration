from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import threading
import time

import httpx
import pytest

from tests.workbench.conftest import P, PASSWORD, _HASH


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_serve_stops_promptly_while_a_browser_holds_the_graph_stream(store, tmp_path):
    """A reload or Ctrl-C stops the worker even while a browser holds an event
    stream open. Uvicorn otherwise waits for every streaming response to end,
    which an event stream never does, so a --reload left the backend accepting
    nothing."""
    store.plan([])
    port = free_port()
    env = {**os.environ, "WORKBENCH_HOME": str(tmp_path / "home"), "WORKBENCH_STORE": str(store.root),
           "WORKBENCH_HULY_PROJECT": "T", "WORKBENCH_SORTIE_URL": "http://127.0.0.1:9",
           "WORKBENCH_PASSWORD_HASH": _HASH, "WORKBENCH_SECRET_KEY": "k",
           "WORKBENCH_RUNTIME_DIR": str(tmp_path / "rt"), "WORKBENCH_FRONTEND_DIR": str(tmp_path / "none")}
    log = open(tmp_path / "serve.log", "w")
    proc = subprocess.Popen([sys.executable, "-m", "workbench.cli", "serve", "--port", str(port)], env=env,
                            stdout=log, stderr=log)
    base = f"http://127.0.0.1:{port}"
    stop = threading.Event()
    opened = threading.Event()

    def browser(cookies):
        # Like EventSource: keep reading until told to stop.
        try:
            with httpx.Client(base_url=base, cookies=cookies, timeout=None) as c:
                with c.stream("GET", f"{P}/events") as r:
                    for _ in r.iter_lines():
                        opened.set()
                        if stop.is_set():
                            return
        except httpx.HTTPError:
            pass  # the server ended the stream as it stopped

    try:
        deadline = time.monotonic() + 15
        while True:
            try:
                httpx.get(f"{base}/api/me", timeout=1)
                break
            except httpx.HTTPError:
                assert time.monotonic() < deadline, "workbench serve did not start"
                time.sleep(0.1)
        login = httpx.post(f"{base}/api/login", json={"password": PASSWORD})
        reader = threading.Thread(target=browser, args=(login.cookies,), daemon=True)
        reader.start()
        assert opened.wait(10)

        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            pytest.fail("workbench serve still waits for the event stream 15s after SIGTERM: "
                        + (tmp_path / "serve.log").read_text()[-300:])
    finally:
        stop.set()
        if proc.poll() is None:
            proc.kill()
            proc.wait()
        log.close()
