from __future__ import annotations

import json

import httpx

from fastapi.testclient import TestClient

from workbench.app import create_app
from workbench.merge import merge
from tests.conftest import breakdown, deliverable
from tests.workbench.conftest import P, PASSWORD, make_config, project, sign_in
from tests.workbench.live import live_server
from tests.workbench.fake_sortie import FakeSortie
from tests.workbench.test_watch import validate_offline, wait_for


def by_key(doc):
    return {n["plan_key"]: n for n in doc["nodes"]}


def billing_store(store):
    store.plan([("billing", [])])
    store.change("billing", breakdown(deliverable("invoice"), deliverable("tax", ["invoice"])))


def test_draft_beside_synced_and_orphan(store):
    billing_store(store)
    fake = FakeSortie()
    epic = fake.issue("billing", kind="epic")
    fake.issue("billing/invoice", parent=epic["id"], state="In Progress", runtime={"status": "running", "turn_count": 2, "last_message": "hi", "attempt": None})
    old = fake.issue("billing/old", parent=epic["id"])
    fake.edges.append({"blocker_id": old["id"], "blocked_id": fake.nodes[1]["id"]})

    app = create_app(make_config(store.root), validate=validate_offline, sortie=fake.client())
    with TestClient(app) as client:
        sign_in(client)
        assert wait_for(lambda: project(app).hub.doc.get("sortie", {}).get("reachable"))
        doc = client.get(f"{P}/graph").json()

    nodes = by_key(doc)
    assert nodes["billing/invoice"]["status"] == "synced"
    assert nodes["billing/invoice"]["tracker"]["state"] == "In Progress"
    assert nodes["billing/invoice"]["runtime"]["status"] == "running"
    assert nodes["billing/tax"]["status"] == "draft" and nodes["billing/tax"]["tracker"] is None
    assert nodes["billing/tax"]["change"] == "billing"
    assert nodes["billing/old"]["status"] == "orphaned"
    assert {"child": "billing/old", "parent": "billing"} in doc["parents"]
    assert {"blocker": "billing/old", "blocked": "billing/invoice"} in doc["blocks"]
    assert doc["sortie"]["capabilities"] == fake.capabilities
    assert doc["validation"]["valid"] is True


def test_sortie_down_keeps_drafts(store):
    billing_store(store)
    fake = FakeSortie()
    fake.down = True
    app = create_app(make_config(store.root), validate=validate_offline, sortie=fake.client())
    with TestClient(app) as client:
        sign_in(client)
        assert wait_for(lambda: project(app).hub.doc.get("sortie", {}).get("error"))
        doc = client.get(f"{P}/graph").json()
    assert doc["sortie"]["reachable"] is False and "tracker down" in doc["sortie"]["error"]
    assert {n["status"] for n in doc["nodes"]} == {"draft"}


def test_polls_runtime_state(store):
    billing_store(store)
    fake = FakeSortie()
    fake.issue("billing", kind="epic")
    app = create_app(make_config(store.root, poll_seconds=0.1), validate=validate_offline, sortie=fake.client())
    with TestClient(app) as client:
        sign_in(client)
        assert wait_for(lambda: by_key(project(app).hub.doc).get("billing", {}).get("status") == "synced")
        fake.nodes[0]["runtime"] = {"status": "retrying", "attempt": 2}
        assert wait_for(lambda: (by_key(project(app).hub.doc)["billing"]["runtime"] or {}).get("status") == "retrying")


def test_events_stream_starts_with_the_graph(store):
    billing_store(store)
    app = create_app(make_config(store.root), validate=validate_offline, sortie=FakeSortie().client())
    with live_server(app) as base, httpx.Client(base_url=base, timeout=5) as client:
        assert client.get(f"{P}/events").status_code == 401
        assert client.post("/api/login", json={"password": PASSWORD}).status_code == 200
        with client.stream("GET", f"{P}/events") as r:
            assert r.headers["content-type"].startswith("text/event-stream")
            lines = r.iter_lines()
            assert next(lines) == "event: graph"
            first = json.loads(next(lines).removeprefix("data: "))
            assert "billing/tax" in by_key(first)

            # A store edit arrives as the next graph event.
            store.change("billing", breakdown(deliverable("invoice"), deliverable("tax", ["invoice"]), deliverable("vat")))
            for line in lines:
                if line.startswith("data: ") and "billing/vat" in by_key(json.loads(line[6:])):
                    break


def test_merge_without_tracker():
    plan = {"nodes": [{"plan_key": "a", "kind": "epic"}], "parents": [], "blocks": [], "unplanned_changes": ["x"]}
    doc = merge(plan, None)
    assert doc["nodes"][0]["status"] == "draft" and doc["unplanned_changes"] == ["x"]
