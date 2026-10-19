from __future__ import annotations

from planlib.validate import validate
from tests.conftest import breakdown, deliverable


def no_openspec(*_):
    raise AssertionError("openspec should not be called")


def codes(result):
    return sorted(e.code for e in result.errors)


def with_specs(store, change, spec_path, *names):
    """Give a change a delta spec and a matching fake `openspec show` payload."""
    d = store.root / "openspec" / "changes" / change / "specs" / spec_path
    d.mkdir(parents=True, exist_ok=True)
    body = "## ADDED Requirements\n\n"
    for n in names:
        body += f"### Requirement: {n}\nIt SHALL {n}.\n\n#### Scenario: s\n- **WHEN** a\n- **THEN** b\n\n"
    (d / "spec.md").write_text(body)
    return {"deltas": [
        {"spec": spec_path, "operation": "ADDED", "requirement": {"text": f"It SHALL {n}."}} for n in names
    ]}


def test_valid_store_has_no_errors(store):
    store.plan([("accounts-api", []), ("billing", ["accounts-api"])])
    store.change("accounts-api", breakdown(deliverable("accounts-close")))
    store.change("billing", breakdown(deliverable("invoice", ["accounts-api/accounts-close"]), deliverable("tax", ["invoice"])))
    assert validate(store.root, show=no_openspec).errors == []


def test_duplicate_id(store):
    store.plan([("billing", [])])
    store.change("billing", breakdown(deliverable("invoice"), deliverable("invoice")))
    r = validate(store.root, show=no_openspec)
    assert codes(r) == ["duplicate_id"]
    assert r.errors[0].deliverable == "invoice" and r.errors[0].change == "billing"


def test_dangling_ref_local_and_cross_change(store):
    store.plan([("accounts-api", []), ("billing", ["accounts-api"])])
    store.change("accounts-api", breakdown(deliverable("open")))
    store.change("billing", breakdown(deliverable("invoice", ["nope", "accounts-api/close"])))
    r = validate(store.root, show=no_openspec)
    assert codes(r) == ["dangling_ref", "dangling_ref"]
    assert {e.members[1] for e in r.errors} == {"billing/nope", "accounts-api/close"}
    assert all(e.file == "openspec/changes/billing/breakdown.yaml" for e in r.errors)


def test_change_in_plan_that_does_not_exist(store):
    store.plan([("billing", []), ("ghost", ["billing"])])
    store.change("billing")
    r = validate(store.root, show=no_openspec)
    assert codes(r) == ["unknown_change"]
    assert r.errors[0].change == "ghost"


def test_plan_dependency_on_unlisted_change(store):
    store.plan([("billing", ["accounts-api"])])
    store.change("billing")
    store.change("accounts-api")
    assert codes(validate(store.root, show=no_openspec)) == ["dangling_change_ref"]


def test_deliverable_cycle_names_all_members(store):
    store.plan([("billing", [])])
    store.change("billing", breakdown(deliverable("a", ["b"]), deliverable("b", ["a"]), deliverable("c", ["a"])))
    r = validate(store.root, show=no_openspec)
    assert codes(r) == ["cycle"]
    assert set(r.errors[0].members) == {"billing/a", "billing/b"}


def test_three_member_cycle_across_changes(store):
    store.plan([("x", ["y"]), ("y", [])])
    store.change("x", breakdown(deliverable("a", ["y/b"]), deliverable("c", ["a"])))
    store.change("y", breakdown(deliverable("b", ["x/c"])))
    r = validate(store.root, show=no_openspec)
    cycles = [e for e in r.errors if e.code == "cycle"]
    assert len(cycles) == 1
    assert set(cycles[0].members) == {"x/a", "x/c", "y/b"}


def test_self_dependency_is_a_cycle(store):
    store.plan([("billing", [])])
    store.change("billing", breakdown(deliverable("a", ["a"])))
    r = validate(store.root, show=no_openspec)
    assert codes(r) == ["cycle"] and r.errors[0].members == ("billing/a",)


def test_epic_cycle(store):
    store.plan([("x", ["y"]), ("y", ["x"])])
    store.change("x")
    store.change("y")
    r = validate(store.root, show=no_openspec)
    assert codes(r) == ["cycle"]
    assert set(r.errors[0].members) == {"x", "y"}
    assert r.errors[0].file == "openspec/plan.yaml"


def test_cross_change_dependency_the_plan_does_not_allow(store):
    store.plan([("billing", []), ("search-index", [])])
    store.change("billing", breakdown(deliverable("invoice", ["search-index/indexer"])))
    store.change("search-index", breakdown(deliverable("indexer")))
    r = validate(store.root, show=no_openspec)
    assert codes(r) == ["cross_change_not_in_plan"]
    e = r.errors[0]
    assert set(e.members) == {"billing/invoice", "search-index/indexer", "billing", "search-index"}
    assert "billing/invoice" in e.message and "search-index/indexer" in e.message


def test_cross_change_dependency_through_another_change(store):
    store.plan([("a", []), ("b", ["a"]), ("c", ["b"])])
    store.change("a", breakdown(deliverable("one")))
    store.change("b")
    store.change("c", breakdown(deliverable("three", ["a/one"])))
    assert validate(store.root, show=no_openspec).errors == []


def test_covers_ref_that_exists(store):
    store.plan([("billing", [])])
    store.change("billing", breakdown(deliverable("invoice", covers=["billing/invoicing#Monthly invoice"])))
    payload = with_specs(store, "billing", "billing/invoicing", "Monthly invoice")
    assert validate(store.root, show=lambda *_: payload).errors == []


def test_covers_ref_that_does_not_exist(store):
    store.plan([("billing", [])])
    store.change(
        "billing",
        breakdown(deliverable("invoice", covers=["billing/invoicing#Yearly invoice", "billing/other#Monthly invoice"])),
    )
    payload = with_specs(store, "billing", "billing/invoicing", "Monthly invoice")
    r = validate(store.root, show=lambda *_: payload)
    assert codes(r) == ["unknown_requirement", "unknown_requirement"]
    assert all(e.deliverable == "invoice" for e in r.errors)


def test_openspec_disagreement_is_an_error_not_a_pass(store):
    store.plan([("billing", [])])
    store.change("billing", breakdown(deliverable("invoice", covers=["billing/invoicing#Monthly invoice"])))
    with_specs(store, "billing", "billing/invoicing", "Monthly invoice")
    r = validate(store.root, show=lambda *_: {"deltas": []})
    assert codes(r) == ["openspec"]


def test_several_problems_at_once(store):
    store.plan([("billing", [])])
    store.change(
        "billing",
        breakdown(deliverable("invoice"), deliverable("invoice"), deliverable("tax", ["missing"])),
    )
    r = validate(store.root, show=no_openspec)
    assert codes(r) == ["dangling_ref", "duplicate_id"]


def test_schema_and_graph_problems_in_one_run(store):
    store.plan([("billing", []), ("ghost", [])])
    store.change("billing", breakdown(deliverable("invoice", kind="task")))
    r = validate(store.root, show=no_openspec)
    assert codes(r) == ["schema", "unknown_change"]


def test_unplanned_change_is_not_an_error(store):
    store.plan([("billing", [])])
    store.change("billing", breakdown(deliverable("invoice")))
    store.change("search-index", breakdown(deliverable("indexer", ["billing/invoice"])))
    assert validate(store.root, show=no_openspec).errors == []
