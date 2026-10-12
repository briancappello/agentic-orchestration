from __future__ import annotations

import time

from fastapi.testclient import TestClient

from workbench.app import create_app
from tests.conftest import breakdown, deliverable
from tests.workbench.conftest import make_config, sign_in


def no_openspec(*_):
    raise AssertionError("openspec should not be called")


def validate_offline(root):
    import planlib

    return planlib.validate(root, show=no_openspec)


def wait_for(predicate, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return predicate()


def keys(graph):
    return {n["plan_key"] for n in graph["nodes"]}


def test_valid_edit_updates_graph_and_cycle_keeps_it(store):
    store.plan([("billing", [])])
    store.change("billing", breakdown(deliverable("invoice")))
    app = create_app(make_config(store.root, debounce_ms=300), validate=validate_offline)

    with TestClient(app) as client:
        sign_in(client)
        state = app.state.plan
        assert keys(state.graph) == {"billing", "billing/invoice"}

        start = time.monotonic()
        store.change("billing", breakdown(deliverable("invoice"), deliverable("tax", ["invoice"])))
        assert wait_for(lambda: state.graph and "billing/tax" in keys(state.graph))
        assert time.monotonic() - start < 2.0

        store.change("billing", breakdown(deliverable("invoice", ["tax"]), deliverable("tax", ["invoice"])))
        assert wait_for(lambda: any(e["code"] == "cycle" for e in state.errors))
        assert keys(state.graph) == {"billing", "billing/invoice", "billing/tax"}
        cycle = next(e for e in state.errors if e["code"] == "cycle")
        assert set(cycle["members"]) == {"billing/invoice", "billing/tax"}

        body = client.get("/api/validation").json()
        assert body["valid"] is False and body["has_graph"] is True


def test_broken_store_reports_without_graph(store):
    app = create_app(make_config(store.root), validate=validate_offline)
    with TestClient(app) as client:
        sign_in(client)
        body = client.get("/api/validation").json()
        assert body["has_graph"] is False and body["errors"][0]["code"] == "missing_plan"
