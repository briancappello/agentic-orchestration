from __future__ import annotations

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


@pytest.fixture
def session_app(store, tmp_path):
    store.plan([])
    prompt = tmp_path / "prompt.md"
    prompt.write_text("You plan in {{store}}.")
    manager = SessionManager(store.root, [BROKER], [sys.executable, str(FAKE_AGENT)], prompt, runtime_dir=tmp_path / "rt")
    app = create_app(make_config(store.root), validate=validate_offline, sortie=FakeSortie().client(), sessions=manager)
    return app, manager


def test_round_trip_permission_and_reattach(session_app):
    app, manager = session_app
    with live_server(app) as base, httpx.Client(base_url=base, timeout=20) as client:
        assert client.get("/api/session").status_code == 401
        assert client.post("/api/login", json={"password": PASSWORD}).status_code == 200

        started = client.post("/api/session").json()
        assert started["active"] is True
        pid = manager.session.process.pid
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

        assert client.delete("/api/session").json() == {"active": False}
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                break
            time.sleep(0.05)
        else:
            raise AssertionError("broker still running after the session ended")
        assert client.post("/api/session/commands", json={"op": "state"}).status_code == 409
