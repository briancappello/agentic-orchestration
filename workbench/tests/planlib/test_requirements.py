from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path

import pytest

from planlib.requirements import RequirementsError, openspec_show, requirement_names
from tests.conftest import FIXTURES

CAPTURED = FIXTURES / "openspec-1.13"
# A real, larger change: plan-to-tracker-dag as archived in the platform spec store.
REAL_CHANGE = Path.home() / "dev" / "agent-platform-specs" / "openspec/changes/archive/2026-10-16-plan-to-tracker-dag"
HAS_OPENSPEC = shutil.which("openspec") is not None


@pytest.fixture
def billing_store(store):
    shutil.copytree(CAPTURED / "billing", store.root / "openspec" / "changes" / "billing")
    return store


def captured_show(_store, change):
    return json.loads((CAPTURED / f"{change}.show.json").read_text())


def test_names_from_captured_1_13_output(billing_store):
    names = requirement_names(billing_store.root, "billing", show=captured_show)
    assert names == {
        "accounts": {"Close account"},
        "billing/invoicing": {"Monthly invoice", "Tax lines"},
    }


def test_header_inside_code_fence_is_ignored(billing_store):
    names = requirement_names(billing_store.root, "billing", show=captured_show)
    assert "not a header" not in names["billing/invoicing"]


def test_unexpected_shape_fails_clearly(billing_store):
    with pytest.raises(RequirementsError, match=r"tested with OpenSpec 1\.13.*'deltas'"):
        requirement_names(billing_store.root, "billing", show=lambda *_: {"items": []})


def test_missing_requirement_text_fails_clearly(billing_store):
    payload = captured_show(None, "billing")
    del payload["deltas"][0]["requirement"]["text"]
    with pytest.raises(RequirementsError, match="requirement.text"):
        requirement_names(billing_store.root, "billing", show=lambda *_: payload)


def test_header_count_disagreement_fails(billing_store):
    payload = captured_show(None, "billing")
    payload["deltas"].append(copy.deepcopy(payload["deltas"][0]))
    with pytest.raises(RequirementsError, match="OpenSpec reports 2"):
        requirement_names(billing_store.root, "billing", show=lambda *_: payload)


def test_header_text_disagreement_fails(billing_store):
    payload = captured_show(None, "billing")
    payload["deltas"][0]["requirement"]["text"] = "Something else entirely."
    with pytest.raises(RequirementsError, match="Close account"):
        requirement_names(billing_store.root, "billing", show=lambda *_: payload)


def test_removed_requirement_is_not_live(store):
    d = store.change("billing")
    spec = d / "specs" / "billing"
    spec.mkdir(parents=True)
    (spec / "spec.md").write_text(
        "## ADDED Requirements\n\n### Requirement: Kept\nIt SHALL stay.\n\n"
        "#### Scenario: s\n- **WHEN** x\n- **THEN** y\n\n"
        "## REMOVED Requirements\n\n### Requirement: Gone\n**Reason**: r\n**Migration**: m\n"
    )
    payload = {"deltas": [
        {"spec": "billing", "operation": "ADDED", "requirement": {"text": "It SHALL stay."}},
        {"spec": "billing", "operation": "REMOVED", "requirement": {"text": "Gone"}},
    ]}
    assert requirement_names(store.root, "billing", show=lambda *_: payload) == {"billing": {"Kept"}}


@pytest.mark.skipif(not HAS_OPENSPEC, reason="openspec not installed")
def test_real_openspec_on_captured_change(billing_store):
    (billing_store.root / "openspec" / "config.yaml").write_text("schema: spec-driven\n")
    names = requirement_names(billing_store.root, "billing", show=openspec_show)
    assert names["billing/invoicing"] == {"Monthly invoice", "Tax lines"}


@pytest.mark.skipif(
    not HAS_OPENSPEC or not REAL_CHANGE.is_dir(),
    reason="openspec or the platform spec store is not available",
)
def test_real_change_in_store(store):
    shutil.copytree(REAL_CHANGE, store.root / "openspec" / "changes" / "plan-to-tracker-dag")
    (store.root / "openspec" / "config.yaml").write_text("schema: spec-driven\n")
    names = requirement_names(store.root, "plan-to-tracker-dag")
    assert "Optional write capabilities" in names["sortie/tracker-write-capabilities"]
    assert sum(len(v) for v in names.values()) == 42


def test_openspec_failure_is_reported(store):
    with pytest.raises(RequirementsError, match="failed|not installed"):
        openspec_show(store.root, "no-such-change")
