"""Build the validated plan-graph document, the only form of the plan that leaves the store."""

from __future__ import annotations

import hashlib
import re
from typing import Any

import networkx as nx

from .approval import approval_state
from .checks import NamesFor, resolve_ref
from .errors import PlanError
from .requirements import RequirementsError
from .schemas import SUPPORTED_VERSIONS, Schemas
from .store import CHANGES_DIR, PLAN_FILE, LoadedStore

_WHY = re.compile(r"^##\s+Why\s*$(.*?)(?=^##\s|\Z)", re.MULTILINE | re.DOTALL)


def source_digest(store: LoadedStore) -> str:
    files: list[tuple[str, bytes]] = []
    if store.plan_raw is not None:
        files.append((str(PLAN_FILE), store.plan_raw))
    files += [(bd.file, bd.raw) for bd in store.breakdowns.values()]
    h = hashlib.sha256()
    for path, raw in sorted(files):
        h.update(path.encode() + b"\0" + str(len(raw)).encode() + b"\0" + raw)
    return "sha256:" + h.hexdigest()


def build_graph(store: LoadedStore, names_for: NamesFor, schemas: Schemas) -> tuple[dict[str, Any] | None, list[PlanError]]:
    """Return the graph document, or the errors that prevent building it.

    Call only after every check passed.
    """
    assert store.plan is not None
    errors: list[PlanError] = []
    nodes: list[dict[str, Any]] = []
    parents: list[dict[str, str]] = []
    blocks: list[dict[str, str]] = []

    planned = [e["name"] for e in store.plan["changes"]]
    epic_graph = nx.DiGraph()
    for entry in store.plan["changes"]:
        epic_graph.add_node(entry["name"])
        for dep in entry["depends_on"]:
            epic_graph.add_edge(dep, entry["name"])
            blocks.append({"blocker": dep, "blocked": entry["name"]})
    epic_depth = _depths(epic_graph)

    for change in planned:
        try:
            has_spec = any(names_for(change).values())
        except RequirementsError as exc:
            errors.append(PlanError("openspec", str(exc), change=change))
            continue
        bd = store.breakdowns.get(change)
        approval = approval_state(bd.doc) if bd else "unplanned"
        nodes.append(
            {
                "plan_key": change,
                "kind": "epic",
                "change": change,
                "title": change,
                "body": _epic_body(store, change),
                "approval": approval,
                "has_spec": has_spec,
                "depth": epic_depth[change],
                "deliverable_kind": None,
                "covers": [],
                "acceptance_criteria": [],
            }
        )
        if bd is None:
            continue

        story_graph = nx.DiGraph()
        for d in bd.doc["deliverables"]:
            key = f"{change}/{d['id']}"
            story_graph.add_node(key)
            for ref in d["depends_on"]:
                blocker = resolve_ref(change, ref)
                blocks.append({"blocker": blocker, "blocked": key})
                if blocker.split("/", 1)[0] == change:
                    story_graph.add_edge(blocker, key)
        story_depth = _depths(story_graph)
        for d in bd.doc["deliverables"]:
            key = f"{change}/{d['id']}"
            nodes.append(
                {
                    "plan_key": key,
                    "kind": "story",
                    "change": change,
                    "title": d["title"],
                    "body": _story_body(d),
                    "approval": approval,
                    "has_spec": bool(d["covers"]),
                    "depth": story_depth[key],
                    "deliverable_kind": d["kind"],
                    "covers": list(d["covers"]),
                    "acceptance_criteria": list(d["acceptance_criteria"]),
                }
            )
            parents.append({"child": key, "parent": change})

    if errors:
        return None, errors
    doc = {
        "schema_version": SUPPORTED_VERSIONS["plan-graph"],
        "source_digest": source_digest(store),
        "nodes": nodes,
        "parents": parents,
        "blocks": blocks,
        "unplanned_changes": [c for c in store.changes if c not in set(planned)],
    }
    problems = schemas.check("plan-graph", doc, file="<plan graph>")
    if problems:  # pragma: no cover - a bug in this module, not in the store
        raise AssertionError("built graph does not match plan-graph.schema.json: " + "; ".join(map(str, problems)))
    return doc, []


def _depths(g: nx.DiGraph) -> dict[str, int]:
    """Column of each node: a node's generation is one past its latest blocker's,
    which is the length of the longest dependency chain ending at it."""
    return {n: i for i, generation in enumerate(nx.topological_generations(g)) for n in generation}


def _epic_body(store: LoadedStore, change: str) -> str:
    body = f"OpenSpec change `{change}`."
    proposal = store.root / CHANGES_DIR / change / "proposal.md"
    if proposal.is_file():
        m = _WHY.search(proposal.read_text())
        if m and m.group(1).strip():
            body += "\n\n## Why\n\n" + m.group(1).strip()
    return body


def _story_body(d: dict) -> str:
    parts = []
    if d.get("notes"):
        parts.append(d["notes"].strip())
    parts.append("## Acceptance criteria\n\n" + "\n".join(f"- {c}" for c in d["acceptance_criteria"]))
    if d["covers"]:
        parts.append("## Covers\n\n" + "\n".join(f"- `{c}`" for c in d["covers"]))
    return "\n\n".join(parts)
