"""Breakdown approval: a digest over the deliverables, so any later edit reads as draft."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import yaml

from .errors import PlanLoadError
from .schemas import Schemas
from .store import BREAKDOWN_FILE, CHANGES_DIR

_STATUS_LINE = re.compile(r"^status:.*$", re.MULTILINE)
_DIGEST_LINE = re.compile(r"^approved_digest:.*\n?", re.MULTILINE)


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def deliverables_digest(doc: dict) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(doc.get("deliverables", []))).hexdigest()


def approval_state(doc: dict) -> str:
    """``approved`` only when the status says so and the digest still matches."""
    if doc.get("status") == "approved" and doc.get("approved_digest") == deliverables_digest(doc):
        return "approved"
    return "draft"


def approve(store: str | Path, change: str, schemas: Schemas | None = None) -> str:
    """Mark a change's breakdown approved, recording the digest of its deliverables.

    Only ``status`` and ``approved_digest`` change; comments and layout stay.
    Returns the digest. Refuses a breakdown that does not match its schema.
    """
    root = Path(store)
    schemas = schemas or Schemas.load(root)
    rel = CHANGES_DIR / change / BREAKDOWN_FILE
    path = root / rel
    if not path.is_file():
        raise PlanLoadError(f"{rel}: change '{change}' has no breakdown")
    text = path.read_text()
    doc = yaml.safe_load(text)
    errors = schemas.check("breakdown", doc, file=str(rel), change=change)
    if errors:
        raise PlanLoadError("cannot approve a breakdown that fails its schema: " + "; ".join(map(str, errors)))

    digest = deliverables_digest(doc)
    text = _DIGEST_LINE.sub("", text)
    if not _STATUS_LINE.search(text):
        raise PlanLoadError(f"{rel}: no top-level status line to update")
    text = _STATUS_LINE.sub(f"status: approved\napproved_digest: {digest}", text, count=1)

    written = yaml.safe_load(text)
    if approval_state(written) != "approved" or written.get("deliverables") != doc.get("deliverables"):
        raise PlanLoadError(f"{rel}: approving would change more than the approval fields")  # pragma: no cover
    path.write_text(text)
    return digest
