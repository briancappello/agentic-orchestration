from __future__ import annotations

import pytest
import yaml

from planlib import PlanLoadError
from planlib.approval import approval_state, approve, deliverables_digest
from tests.conftest import breakdown, deliverable


def read(path):
    return yaml.safe_load(path.read_text())


def test_draft_reads_as_draft():
    assert approval_state(breakdown(deliverable("a"))) == "draft"


def test_approve_then_edit_then_approve(store):
    d = store.change("billing", breakdown(deliverable("invoice")))
    f = d / "breakdown.yaml"

    digest = approve(store.root, "billing")
    doc = read(f)
    assert doc["status"] == "approved" and doc["approved_digest"] == digest
    assert approval_state(doc) == "approved"

    doc["deliverables"].append(deliverable("tax", ["invoice"]))
    f.write_text(yaml.safe_dump(doc, sort_keys=False))
    edited = read(f)
    assert edited["status"] == "approved"
    assert approval_state(edited) == "draft"

    approve(store.root, "billing")
    assert approval_state(read(f)) == "approved"


def test_digest_ignores_key_order_but_not_values():
    a = breakdown(deliverable("x"))
    b = {"deliverables": [dict(reversed(list(a["deliverables"][0].items())))]}
    assert deliverables_digest(a) == deliverables_digest(b)
    b["deliverables"][0]["title"] = "Other"
    assert deliverables_digest(a) != deliverables_digest(b)


def test_approve_keeps_comments_and_layout(store):
    text = (
        "# reviewed with finance\n"
        "schema_version: 1\n"
        "status: draft\n"
        "deliverables:\n"
        "  - id: invoice  # the first one\n"
        "    title: Invoice\n"
        "    kind: story\n"
        "    depends_on: []\n"
        "    covers: []\n"
        "    acceptance_criteria: [works]\n"
    )
    d = store.change("billing", text)
    approve(store.root, "billing")
    out = (d / "breakdown.yaml").read_text()
    assert "# reviewed with finance" in out and "# the first one" in out
    assert "status: approved\napproved_digest: sha256:" in out


def test_approve_refuses_invalid_breakdown(store):
    store.change("billing", breakdown(deliverable("invoice", kind="task")))
    with pytest.raises(PlanLoadError, match="fails its schema"):
        approve(store.root, "billing")


def test_approve_refuses_missing_breakdown(store):
    store.change("billing")
    with pytest.raises(PlanLoadError, match="no breakdown"):
        approve(store.root, "billing")
