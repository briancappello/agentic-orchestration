from __future__ import annotations

import json
from pathlib import Path

import pytest

from planlib import PlanLoadError, Schemas, load_store
from tests.conftest import FIXTURES, breakdown, deliverable

# The schemas every new project store is created with.
STORE_SCHEMAS = Path(__file__).resolve().parents[2] / "src/workbench/store_template/openspec/schemas/planning"


def test_loads_plan_and_breakdowns(store):
    store.plan([("accounts-api", []), ("billing", ["accounts-api"])])
    store.change("accounts-api", breakdown(deliverable("close")))
    store.change("billing")

    loaded = load_store(store.root)

    assert loaded.errors == []
    assert loaded.changes == ["accounts-api", "billing"]
    assert [c["name"] for c in loaded.plan["changes"]] == ["accounts-api", "billing"]
    assert set(loaded.breakdowns) == {"accounts-api"}


def test_archived_changes_are_not_active(store):
    store.plan([])
    (store.root / "openspec" / "changes" / "archive" / "old").mkdir(parents=True)
    assert load_store(store.root).changes == []


def test_missing_plan_is_reported(store):
    loaded = load_store(store.root)
    assert [e.code for e in loaded.errors] == ["missing_plan"]


def test_newer_breakdown_version_names_both_versions(store):
    store.plan([("billing", [])])
    store.change("billing", breakdown(deliverable("invoice"), schema_version=2))

    loaded = load_store(store.root)

    assert len(loaded.errors) == 1
    err = loaded.errors[0]
    assert err.code == "unsupported_version"
    assert "2" in err.message and "1" in err.message
    assert err.change == "billing"
    assert "billing" not in loaded.breakdowns


def test_newer_plan_version_is_refused(store):
    store.plan({"schema_version": 3, "changes": []})
    loaded = load_store(store.root)
    assert [e.code for e in loaded.errors] == ["unsupported_version"]
    assert "3" in loaded.errors[0].message and "1" in loaded.errors[0].message
    assert loaded.plan is None


def test_newer_store_schema_is_refused(store):
    path = store.root / "openspec/schemas/planning/breakdown.schema.json"
    schema = json.loads(path.read_text())
    schema["properties"]["schema_version"]["const"] = 2
    path.write_text(json.dumps(schema))

    with pytest.raises(PlanLoadError, match=r"version 2.*version 1"):
        Schemas.load(store.root)


def test_missing_schema_is_refused(store):
    (store.root / "openspec/schemas/planning/plan.schema.json").unlink()
    with pytest.raises(PlanLoadError, match="not found"):
        Schemas.load(store.root)


def test_unknown_field_names_deliverable_and_field(store):
    store.plan([("billing", [])])
    store.change("billing", breakdown(deliverable("invoice", owner="me")))

    errs = load_store(store.root).errors

    assert len(errs) == 1
    assert errs[0].code == "schema"
    assert errs[0].deliverable == "invoice"
    assert "owner" in errs[0].message
    assert errs[0].file == "openspec/changes/billing/breakdown.yaml"


def test_bad_kind_names_deliverable_and_field(store):
    store.plan([("billing", [])])
    store.change("billing", breakdown(deliverable("invoice", kind="task")))

    errs = load_store(store.root).errors

    assert len(errs) == 1
    assert errs[0].deliverable == "invoice"
    assert "kind" in errs[0].message


def test_unknown_plan_field_names_change(store):
    store.plan({"schema_version": 1, "changes": [{"name": "billing", "depends_on": [], "owner": "me"}]})
    errs = load_store(store.root).errors
    assert len(errs) == 1 and errs[0].change == "billing" and "owner" in errs[0].message


def test_invalid_yaml_is_reported(store):
    store.plan("schema_version: [1\n")
    assert [e.code for e in load_store(store.root).errors] == ["yaml"]


def test_fixture_schemas_match_the_store_template():
    fixtures = sorted((FIXTURES / "schemas").glob("*.schema.json"))
    assert fixtures
    for f in fixtures:
        assert json.loads(f.read_text()) == json.loads((STORE_SCHEMAS / f.name).read_text()), f.name
