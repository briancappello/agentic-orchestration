from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
import time
from pathlib import Path

import httpx
import pytest

from workbench.app import create_app
from workbench.sessions import SessionManager
from tests.workbench.conftest import PASSWORD, make_config
from tests.workbench.fake_sortie import FakeSortie
from tests.workbench.live import live_server
from tests.workbench.test_watch import validate_offline

BROKER = os.environ.get("WORKBENCH_TEST_BROKER") or shutil.which("acp-broker")
FAKE_AGENT = Path(__file__).parent / "fixtures" / "fake_acp_agent.py"

pytestmark = pytest.mark.skipif(not BROKER, reason="set WORKBENCH_TEST_BROKER or put acp-broker on PATH")


def events(stream):
    """Yield (id, event) pairs from an SSE line iterator."""
    event_id = None
    for line in stream:
        if line.startswith("id: "):
            event_id = line[4:]
        elif line.startswith("data: "):
            yield event_id, json.loads(line[6:])
            event_id = None


def until(gen, predicate, limit=200):
    seen = []
    for pair in gen:
        seen.append(pair)
        if predicate(pair[1]):
            return pair, seen
        if len(seen) > limit:
            break
    raise AssertionError(f"event not seen; got {[e for _, e in seen][-5:]}")


def text_of(ev):
    if ev.get("type") != "update":
        return ""
    upd = ev.get("update") or ev.get("params", {}).get("update") or {}
    if "update" in ev.get("data", {}):
        upd = ev["data"]["update"]
    content = upd.get("content") or {}
    return content.get("text", "") if isinstance(content, dict) else ""


def flat(ev):
    return json.dumps(ev)


def make_app(store, tmp_path):
    prompt = tmp_path / "prompt.md"
    prompt.write_text("You plan in {{store}}.")
    manager = SessionManager(store.root, [BROKER], [sys.executable, str(FAKE_AGENT)], prompt, runtime_dir=tmp_path / "rt")
    app = create_app(make_config(store.root), validate=validate_offline, sortie=FakeSortie().client(), sessions=manager)
    return app, manager


def broker_pid(manager):
    return json.loads((manager.runtime_dir / "state.json").read_text())["broker_pid"]


def wait_dead(pid, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        time.sleep(0.05)
    return False


@pytest.fixture
def session_app(store, tmp_path):
    store.plan([])
    app, manager = make_app(store, tmp_path)
    yield app, manager
    asyncio.run(manager.stop())


def test_round_trip_permission_and_reattach(session_app):
    app, manager = session_app
    with live_server(app) as base, httpx.Client(base_url=base, timeout=20) as client:
        assert client.get("/api/session").status_code == 401
        assert client.post("/api/login", json={"password": PASSWORD}).status_code == 200

        started = client.post("/api/session").json()
        assert started["active"] is True
        pid = broker_pid(manager)
        rec = next((manager.runtime_dir / "registry").glob(f"{started['key']}.*.json"))
        assert json.loads(rec.read_text())["pid"] == pid

        with client.stream("GET", "/api/session/events") as r:
            gen = events(r.iter_lines())
            # The planning prompt went out as the first turn, with the store path.
            until(gen, lambda e: "echo: You plan in " in flat(e))

            assert client.post("/api/session/commands", json={"op": "steer", "text": "hello agent"}).status_code == 200
            (last_id, _), _ = until(gen, lambda e: "echo: hello agent" in flat(e))

            client.post("/api/session/commands", json={"op": "steer", "text": "ASK-PERMISSION please"})
            (_, perm), _ = until(gen, lambda e: e.get("type") == "permission")
            perm_id = perm.get("id") or perm.get("data", {}).get("id")
            assert perm_id is not None, perm
            r2 = client.post("/api/session/commands", json={"op": "permit", "id": perm_id, "option": "allow"})
            assert r2.status_code == 200, r2.text
            until(gen, lambda e: "permission: " in flat(e) and "selected" in flat(e) and "allow" in flat(e))

        # A reload reattaches: a fresh stream replays the history, and one
        # with Last-Event-ID gets only what came after.
        with client.stream("GET", "/api/session/events") as r:
            until(events(r.iter_lines()), lambda e: "echo: hello agent" in flat(e))
        with client.stream("GET", "/api/session/events", headers={"Last-Event-ID": last_id}) as r:
            (_, ev), seen = until(events(r.iter_lines()), lambda e: "permission:" in flat(e))
            assert not any("echo: hello agent" in flat(e) for _, e in seen)

        assert client.post("/api/session/commands", json={"op": "rm -rf"}).status_code == 400
        texts = [m["text"] for m in client.get("/api/session").json()["messages"]]
        assert texts == ["hello agent", "ASK-PERMISSION please"]

        assert client.delete("/api/session").json() == {"active": False}
        assert wait_dead(pid), "broker still running after the session ended"
        assert client.post("/api/session/commands", json={"op": "state"}).status_code == 409


def test_session_survives_a_backend_restart(store, tmp_path):
    store.plan([])
    app, manager = make_app(store, tmp_path)
    try:
        with live_server(app) as base, httpx.Client(base_url=base, timeout=20) as client:
            client.post("/api/login", json={"password": PASSWORD})
            client.post("/api/session")
            pid = broker_pid(manager)
            with client.stream("GET", "/api/session/events") as r:
                gen = events(r.iter_lines())
                until(gen, lambda e: "echo: You plan in " in flat(e))
                client.post("/api/session/commands", json={"op": "steer", "text": "before restart"})
                until(gen, lambda e: "echo: before restart" in flat(e))
        # The first backend is gone: its server and lifespan have shut down.

        app2, manager2 = make_app(store, tmp_path)
        with live_server(app2) as base, httpx.Client(base_url=base, timeout=20) as client:
            client.post("/api/login", json={"password": PASSWORD})
            status = client.get("/api/session").json()
            assert status["active"] is True and broker_pid(manager2) == pid
            assert [m["text"] for m in status["messages"]] == ["before restart"]
            with client.stream("GET", "/api/session/events") as r:
                gen = events(r.iter_lines())
                until(gen, lambda e: "echo: before restart" in flat(e))  # replayed history
                client.post("/api/session/commands", json={"op": "steer", "text": "after restart"})
                until(gen, lambda e: "echo: after restart" in flat(e))
            assert client.delete("/api/session").json() == {"active": False}
        assert wait_dead(pid)
    finally:
        asyncio.run(manager.stop())


def test_a_dead_session_reads_as_ended_and_restarts(store, tmp_path):
    store.plan([])
    app, manager = make_app(store, tmp_path)
    try:
        with live_server(app) as base, httpx.Client(base_url=base, timeout=20) as client:
            client.post("/api/login", json={"password": PASSWORD})
            client.post("/api/session")
            pid = broker_pid(manager)
            os.kill(pid, 9)
            assert wait_dead(pid)
            deadline = time.monotonic() + 10
            while client.get("/api/session").json()["active"] and time.monotonic() < deadline:
                time.sleep(0.05)
            assert client.get("/api/session").json()["active"] is False
            assert client.post("/api/session/commands", json={"op": "state"}).status_code == 409
            assert client.post("/api/session").json()["active"] is True
            assert broker_pid(manager) != pid
    finally:
        asyncio.run(manager.stop())
