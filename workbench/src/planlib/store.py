"""Read a spec store's planning files: the plan of plans and each change's breakdown."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .errors import PlanError
from .schemas import Schemas

PLAN_FILE = Path("openspec") / "plan.yaml"
CHANGES_DIR = Path("openspec") / "changes"
BREAKDOWN_FILE = "breakdown.yaml"


@dataclass
class Breakdown:
    change: str
    file: str
    raw: bytes
    doc: dict[str, Any]


@dataclass
class LoadedStore:
    """Everything read from the store, plus the problems found while reading.

    ``plan`` and a change's entry in ``breakdowns`` are set only when the file
    parsed and matched its schema, so later checks never see malformed data.
    """

    root: Path
    changes: list[str]
    plan: dict[str, Any] | None = None
    plan_raw: bytes | None = None
    breakdowns: dict[str, Breakdown] = field(default_factory=dict)
    errors: list[PlanError] = field(default_factory=list)


def active_changes(root: Path) -> list[str]:
    changes_dir = Path(root) / CHANGES_DIR
    if not changes_dir.is_dir():
        return []
    return sorted(
        p.name for p in changes_dir.iterdir() if p.is_dir() and p.name != "archive" and not p.name.startswith(".")
    )


def load_store(root: Path, schemas: Schemas | None = None) -> LoadedStore:
    root = Path(root)
    schemas = schemas or Schemas.load(root)
    store = LoadedStore(root=root, changes=active_changes(root))

    plan_path = root / PLAN_FILE
    if not plan_path.is_file():
        store.errors.append(PlanError("missing_plan", "the store has no plan file", file=str(PLAN_FILE)))
    else:
        raw = plan_path.read_bytes()
        doc, errs = _parse_and_check(schemas, "plan", raw, file=str(PLAN_FILE), change=None)
        store.errors.extend(errs)
        if doc is not None:
            store.plan = doc
            store.plan_raw = raw

    for change in store.changes:
        rel = CHANGES_DIR / change / BREAKDOWN_FILE
        path = root / rel
        if not path.is_file():
            continue
        raw = path.read_bytes()
        doc, errs = _parse_and_check(schemas, "breakdown", raw, file=str(rel), change=change)
        store.errors.extend(errs)
        if doc is not None:
            store.breakdowns[change] = Breakdown(change=change, file=str(rel), raw=raw, doc=doc)
    return store


def _parse_and_check(
    schemas: Schemas, kind: str, raw: bytes, *, file: str, change: str | None
) -> tuple[dict | None, list[PlanError]]:
    try:
        doc = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        return None, [PlanError("yaml", f"not valid YAML: {exc}", file=file, change=change)]
    errs = schemas.check(kind, doc, file=file, change=change)
    return (doc if not errs else None), errs
