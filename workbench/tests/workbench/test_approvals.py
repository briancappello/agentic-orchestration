from __future__ import annotations

import json

import jsonschema
import planlib
import yaml
from fastapi.testclient import TestClient

from tests.conftest import breakdown, deliverable
from tests.workbench.conftest import P, make_config, project, settle, sign_in
from tests.workbench.fake_oidc import CLIENT_ID, CLIENT_SECRET, ISSUER, REDIRECT, FakeProvider
from tests.workbench.fake_sortie import FakeSortie
from tests.workbench.test_identity import sign_in_oidc
from tests.workbench.test_watch import validate_offline
from workbench.app import create_app
from workbench.oidc import OIDCClient

STATES = {"release": "Todo", "backlog": "Backlog", "cancel": "Canceled", "done": "Done"}


def billing(store, *extra):
    store.plan([("accounts", []), ("billing", ["accounts"])])
    store.change("accounts", breakdown(deliverable("a3")))
    store.change("billing", breakdown(deliverable("b1", ["accounts/a3"]), deliverable("b2"), *extra))


def app_for(store, fake, **cfg):
    return create_app(make_config(store.root, **cfg), validate=validate_offline, sortie=fake.client())


def status(app, key):
    return next(n for n in project(app).hub.doc["nodes"] if n["plan_key"] == key)


def test_held_ready_and_the_sync_graph(store):
    billing(store)
    fake = FakeSortie()
    fake.plan_states = STATES
    app = app_for(store, fake)
    with TestClient(app) as client:
        sign_in(client)
        assert status(app, "billing/b1")["plan_status"] == "draft"
        assert client.post(f"{P}/approve", json={"epic": "billing"}).status_code == 200
        b1, b2 = status(app, "billing/b1"), status(app, "billing/b2")
        assert b1["plan_status"] == "held" and b1["held_by"] == ["accounts/a3"]
        assert b2["plan_status"] == "ready" and b2["approved_by"]["id"] == "local|operator" and b2["review"] == "human"

        assert client.post(f"{P}/approve", json={"keys": ["accounts/a3"]}).status_code == 200
        assert status(app, "billing/b1")["plan_status"] == "ready"

        client.post(f"{P}/sync/preview")
        graph = next(r[2]["graph"] for r in fake.requests if r[1] == "/api/v1/plan/sync")
        schema = json.loads((store.root / "openspec/schemas/planning/plan-graph.schema.json").read_text())
        jsonschema.validate(graph, schema)
        nodes = {n["plan_key"]: n for n in graph["nodes"]}
        assert graph["schema_version"] == 2
        assert nodes["billing/b1"]["release"] is True and nodes["billing/b1"]["approved_by"]["name"] == "Local operator"
        assert "digest" not in nodes["billing/b1"] and "plan_status" not in nodes["billing/b1"]


def test_frozen_story_edit_is_refused(store):
    billing(store)
    fake = FakeSortie()
    fake.plan_states = STATES
    fake.issue("billing/b2", state="In Progress", runtime={"status": "running"})
    app = app_for(store, fake)
    with TestClient(app) as client:
        sign_in(client)
        client.post(f"{P}/approve", json={"epic": "billing"})
        project(app).hub.frozen = {}
        settle(client)
        assert status(app, "billing/b2")["plan_status"] == "frozen"
        store.change("billing", breakdown(deliverable("b1", ["accounts/a3"]), deliverable("b2", title="Changed")))
        settle(client)
        assert any(e["code"] == "frozen" for e in project(app).plan.errors)


def test_an_edit_to_a_released_story_pulls_it_back(store):
    billing(store)
    fake = FakeSortie()
    fake.plan_states = STATES
    fake.issue("billing/b2", state="Todo")
    app = app_for(store, fake)
    with TestClient(app) as client:
        sign_in(client)
        settle(client)
        client.post(f"{P}/approve", json={"epic": "billing"})
        assert status(app, "billing/b2")["plan_status"] == "released"
        store.change("billing", breakdown(deliverable("b1", ["accounts/a3"]), deliverable("b2", title="Edited")))
        settle(client)
        assert fake.pulled_back == ["billing/b2"]
        # The next poll sees the story back in the backlog.
        settle(client)
        assert status(app, "billing/b2")["plan_status"] == "draft"


def test_cancel_sends_dependents_to_rereview(store):
    store.plan([("billing", [])])
    store.change("billing", breakdown(deliverable("a3"), deliverable("b1", ["a3"]), deliverable("c1", ["b1"])))
    fake = FakeSortie()
    fake.plan_states = STATES
    fake.issue("billing/a3", state="In Progress", runtime={"status": "running"})
    app = app_for(store, fake)
    with TestClient(app) as client:
        sign_in(client)
        client.post(f"{P}/approve", json={"epic": "billing"})
        r = client.post(f"{P}/stories/cancel", json={"key": "billing/a3"})
        assert r.status_code == 200 and r.json()["rereview"] == ["billing/b1"] and fake.cancelled == ["billing/a3"]
        b1 = status(app, "billing/b1")
        assert b1["plan_status"] == "needs_rereview" and b1["rereview"] == {"reason": "blocker_canceled", "ref": "billing/a3"}
        assert status(app, "billing/c1")["plan_status"] == "held"
        client.post(f"{P}/approve", json={"keys": ["billing/b1"]})
        assert status(app, "billing/b1")["plan_status"] in ("held", "ready")


def test_supersede_cancels_the_replaced_story_and_keeps_dependents(store):
    store.plan([("billing", [])])
    store.change("billing", breakdown(deliverable("a3"), deliverable("b1", ["a3"])))
    fake = FakeSortie()
    fake.plan_states = STATES
    app = app_for(store, fake)
    with TestClient(app) as client:
        sign_in(client)
        client.post(f"{P}/approve", json={"epic": "billing"})
        store.change("billing", breakdown(deliverable("a3"), deliverable("a3b", supersedes="a3"), deliverable("b1", ["a3"])))
        settle(client)
        assert "billing/a3b" in project(app).plan.stories
        assert client.post(f"{P}/stories/supersede", json={"key": "billing/a3b"}).json()["error"]["code"] == "replacement_draft"
        client.post(f"{P}/approve", json={"keys": ["billing/a3b"]})
        fake.issue("billing/a3")
        r = client.post(f"{P}/stories/supersede", json={"key": "billing/a3b"})
        assert r.status_code == 200 and fake.cancelled == ["billing/a3"]
        assert status(app, "billing/b1")["approval"] == "approved"
        blocks = {(b["blocker"], b["blocked"]) for b in project(app).plan.graph["blocks"]}
        assert ("billing/a3b", "billing/b1") in blocks


def test_pull_back_losing_to_a_claim(store):
    billing(store)
    fake = FakeSortie()
    fake.plan_states = STATES
    fake.issue("billing/b2", state="Todo")
    fake.claimed.add("billing/b2")
    app = app_for(store, fake)
    with TestClient(app) as client:
        sign_in(client)
        r = client.post(f"{P}/stories/pull-back", json={"key": "billing/b2"})
        assert r.status_code == 409 and r.json()["error"]["code"] == "already_claimed"


def test_unverified_claim_needs_rereview(store):
    billing(store)
    fake = FakeSortie()
    fake.plan_states = STATES
    fake.issue("billing/b2", state="Done", terminal=True, satisfaction="unverified_no_change", unverified_reason="no_mirror")
    app = app_for(store, fake)
    with TestClient(app) as client:
        sign_in(client)
        settle(client)
        assert status(app, "billing/b2")["rereview"] == {"reason": "unverified_no_change", "ref": "no_mirror"}


def test_planner_cannot_act(store, tmp_path):
    billing(store)
    provider = FakeProvider()
    provider.claims["groups"] = ["eng"]
    cfg = make_config(store.root, password_hash="", oidc_issuer=ISSUER, oidc_client_id=CLIENT_ID, oidc_client_secret=CLIENT_SECRET,
                      oidc_redirect_url=REDIRECT, oidc_planner_group="eng", oidc_approver_group="plan-approvers")
    app = create_app(cfg, validate=validate_offline, sortie=FakeSortie().client(),
                     oidc=OIDCClient(ISSUER, CLIENT_ID, CLIENT_SECRET, REDIRECT, transport=provider.transport()))
    with TestClient(app) as client:
        sign_in_oidc(client, provider)
        for path, body in [("approve", {"epic": "billing"}), ("stories/pull-back", {"key": "billing/b2"}),
                           ("stories/cancel", {"key": "billing/b2"}), ("stories/supersede", {"key": "billing/b2"})]:
            r = client.post(f"{P}/{path}", json=body)
            assert r.status_code == 403 and r.json()["error"]["code"] == "role_required", path
        assert project(app).registry.approvals(project(app).project.id) == {}


def test_old_approvals_are_imported_once(store):
    store.plan([("billing", [])])
    doc = breakdown(deliverable("a"), deliverable("b"))
    doc.update(status="approved", approved_digest=planlib.deliverables_digest(doc))
    store.change("billing", doc)
    fake = FakeSortie()
    app = app_for(store, fake)
    with TestClient(app) as client:
        sign_in(client)
        rows = project(app).registry.approvals(project(app).project.id)
        assert set(rows) == {"billing/a", "billing/b"} and rows["billing/a"]["approver_id"] == "migration|billing"
        assert status(app, "billing/a")["approval"] == "approved"
