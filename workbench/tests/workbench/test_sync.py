from __future__ import annotations

import planlib
from fastapi.testclient import TestClient

from workbench.app import create_app
from tests.conftest import breakdown, deliverable
from tests.workbench.conftest import P, make_config, project, sign_in
from tests.workbench.fake_sortie import FakeSortie
from tests.workbench.test_watch import validate_offline, wait_for


def setup(store, fake):
    store.plan([("billing", [])])
    store.change("billing", breakdown(deliverable("invoice"), deliverable("tax", ["invoice"])))
    app = create_app(make_config(store.root), validate=validate_offline, sortie=fake.client())
    return app


def applies(fake):
    return [r for r in fake.requests if r[1] == "/api/v1/plan/sync" and r[2].get("apply")]


def test_nothing_reaches_apply_without_confirmation(store):
    fake = FakeSortie()
    with TestClient(setup(store, fake)) as client:
        sign_in(client)
        r = client.post(f"{P}/sync/preview")
        assert r.status_code == 200 and r.json()["can_apply"] is True
        pid = r.json()["preview_id"]
        assert r.json()["preview"]["counts"]["relations_added"] == 1

        r = client.post(f"{P}/sync/apply", json={"preview_id": pid})
        assert r.status_code == 400 and r.json()["error"]["code"] == "not_confirmed"
        assert applies(fake) == []

        r = client.post(f"{P}/sync/apply", json={"preview_id": pid, "confirm": True})
        assert r.status_code == 200, r.text
        assert len(applies(fake)) == 1 and applies(fake)[0][2]["preview_id"] == pid

        # The preview is used up.
        r = client.post(f"{P}/sync/apply", json={"preview_id": pid, "confirm": True})
        assert r.status_code == 409


def test_missing_capability_blocks_apply(store):
    fake = FakeSortie()
    fake.capabilities = ["create_issue", "set_parent"]
    with TestClient(setup(store, fake)) as client:
        sign_in(client)
        r = client.post(f"{P}/sync/preview").json()
        assert r["can_apply"] is False and r["preview"]["missing_capabilities"] == ["link_dependency"]
        r = client.post(f"{P}/sync/apply", json={"preview_id": r["preview_id"], "confirm": True})
        assert r.status_code == 422 and "link_dependency" in r.json()["error"]["message"]
        assert applies(fake) == []


def test_invalid_plan_cannot_be_previewed(store):
    fake = FakeSortie()
    app = setup(store, fake)
    store.change("billing", breakdown(deliverable("a", ["a"])))
    with TestClient(app) as client:
        sign_in(client)
        r = client.post(f"{P}/sync/preview")
        assert r.status_code == 409 and r.json()["error"]["code"] == "plan_invalid"
        assert not [x for x in fake.requests if x[1] == "/api/v1/plan/sync"]


def test_approve_then_edit_returns_to_draft(store):
    fake = FakeSortie()
    app = setup(store, fake)
    with TestClient(app) as client:
        sign_in(client)
        approval = lambda: {n["plan_key"]: n["approval"] for n in project(app).plan.graph["nodes"]}["billing"]  # noqa: E731
        assert approval() == "draft"

        r = client.post(f"{P}/approve", json={"change": "billing"})
        assert r.status_code == 200 and r.json()["approved_digest"].startswith("sha256:")
        assert approval() == "approved"

        doc = planlib.load_store(store.root).breakdowns["billing"].doc
        doc["deliverables"].append(deliverable("vat"))
        store.change("billing", doc)
        assert wait_for(lambda: approval() == "draft")

        r = client.post(f"{P}/approve", json={"change": "nope"})
        assert r.status_code == 422
