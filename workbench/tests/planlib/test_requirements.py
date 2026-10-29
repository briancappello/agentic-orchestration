from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path

import pytest

from planlib.requirements import RequirementsError, openspec_show, requirement_details, requirement_names
from tests.conftest import FIXTURES

CAPTURED = FIXTURES / "openspec-1.13"
# A real, larger change: plan-to-tracker-dag as archived in the platform spec store.
# An archived change in the repository's own spec store, specs/.
REAL_CHANGE = Path(__file__).resolve().parents[3] / "specs/openspec/changes/archive/2026-10-16-plan-to-tracker-dag"
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


@pytest.mark.skipif(not HAS_OPENSPEC, reason="openspec not installed")
def test_real_change_in_store(store):
    shutil.copytree(REAL_CHANGE, store.root / "openspec" / "changes" / "plan-to-tracker-dag")
    (store.root / "openspec" / "config.yaml").write_text("schema: spec-driven\n")
    names = requirement_names(store.root, "plan-to-tracker-dag")
    assert "Optional write capabilities" in names["sortie/tracker-write-capabilities"]
    assert sum(len(v) for v in names.values()) == 42


def test_openspec_failure_is_reported(store):
    with pytest.raises(RequirementsError, match="failed|not installed"):
        openspec_show(store.root, "no-such-change")


def test_details_read_as_people_read_them(billing_store):
    details = requirement_details(billing_store.root, "billing")
    assert sorted(details) == ["accounts", "billing/invoicing"]
    monthly, tax = details["billing/invoicing"]
    assert monthly["name"] == "Monthly invoice" and monthly["operation"] == "ADDED"
    assert monthly["text"].startswith("The system SHALL generate an invoice") and "immutable once sent" in monthly["text"]
    assert monthly["scenarios"] == [{"name": "First of the month", "steps": [
        {"keyword": "WHEN", "text": "the clock reaches the first day of a month"},
        {"keyword": "THEN", "text": "an invoice exists for every active account"},
    ]}]
    # A header inside a code fence is text, not a requirement; the fence stays in the text.
    assert tax["name"] == "Tax lines" and "### Requirement: not a header" in tax["text"]
    assert [s["name"] for s in tax["scenarios"]] == ["Tax applied"]


def test_details_leave_out_removed_requirements(store):
    spec = store.change("billing") / "specs" / "billing"
    spec.mkdir(parents=True)
    (spec / "spec.md").write_text(
        "## ADDED Requirements\n\n### Requirement: Kept\nIt SHALL stay.\n\n"
        "#### Scenario: s\n- **WHEN** x\n  and more of x\n- **THEN** y\n\n"
        "## REMOVED Requirements\n\n### Requirement: Gone\n**Reason**: r\n**Migration**: m\n"
    )
    assert requirement_details(store.root, "billing") == {"billing": [{
        "name": "Kept", "operation": "ADDED", "text": "It SHALL stay.",
        "scenarios": [{"name": "s", "steps": [{"keyword": "WHEN", "text": "x and more of x"}, {"keyword": "THEN", "text": "y"}]}],
    }]}
    assert requirement_details(store.root, "no-such-change") == {}
