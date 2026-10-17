from __future__ import annotations

from planlib import validate
from tests.conftest import breakdown, deliverable


def no_openspec(*_):
    raise AssertionError("openspec should not be called")


def setup(store, *deliverables):
    store.plan([("billing", [])])
    store.change("billing", breakdown(*deliverables))


def test_an_edit_to_a_frozen_story_is_refused(store):
    setup(store, deliverable("a3"), deliverable("b1", ["a3"]))
    frozen = {"billing/a3": validate(store.root, show=no_openspec).stories["billing/a3"]["digest"]}
    setup(store, deliverable("a3", title="Renamed"), deliverable("b1", ["a3"]))
    r = validate(store.root, show=no_openspec, frozen=frozen)
    assert [e.code for e in r.errors] == ["frozen"] and r.errors[0].deliverable == "a3" and r.graph is None


def test_a_frozen_story_removed_is_refused(store):
    setup(store, deliverable("a3"), deliverable("b1"))
    frozen = {"billing/a3": validate(store.root, show=no_openspec).stories["billing/a3"]["digest"]}
    setup(store, deliverable("b1"))
    r = validate(store.root, show=no_openspec, frozen=frozen)
    assert [e.code for e in r.errors] == ["frozen"] and "billing/a3" in r.errors[0].members


def test_an_unchanged_frozen_story_passes(store):
    setup(store, deliverable("a3"))
    frozen = {"billing/a3": validate(store.root, show=no_openspec).stories["billing/a3"]["digest"]}
    assert validate(store.root, show=no_openspec, frozen=frozen).errors == []


def test_supersede_moves_the_dependents(store):
    setup(store, deliverable("a3"), deliverable("a3b", supersedes="a3"), deliverable("b1", ["a3"]))
    r = validate(store.root, show=no_openspec)
    assert r.errors == []
    blocks = {(b["blocker"], b["blocked"]) for b in r.graph["blocks"]}
    assert ("billing/a3b", "billing/b1") in blocks and ("billing/a3", "billing/b1") not in blocks
    assert r.stories["billing/a3b"]["supersedes"] == "billing/a3"


def test_bad_supersedes(store):
    setup(store, deliverable("a"), deliverable("self", supersedes="self"), deliverable("ghost", supersedes="nope"),
          deliverable("one", supersedes="a"), deliverable("two", supersedes="a"))
    codes = sorted((e.code, e.deliverable) for e in validate(store.root, show=no_openspec).errors)
    assert codes == [("bad_supersedes", "ghost"), ("bad_supersedes", "self"), ("bad_supersedes", "two")]


def test_amend_is_just_a_dependent(store):
    setup(store, deliverable("a3"), deliverable("a3-rounding", ["a3"]))
    blocks = {(b["blocker"], b["blocked"]) for b in validate(store.root, show=no_openspec).graph["blocks"]}
    assert ("billing/a3", "billing/a3-rounding") in blocks


def test_a_breakdown_without_status_passes_the_schema(store):
    store.plan([("billing", [])])
    doc = breakdown(deliverable("a"))
    del doc["status"]
    store.change("billing", doc)
    assert validate(store.root, show=no_openspec).errors == []
