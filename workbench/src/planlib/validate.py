"""The validator's entry point: schema check, then graph checks, then the graph document."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .checks import check_frozen, check_graph, make_names_for
from .graph import build_graph
from .errors import PlanError
from .requirements import openspec_show
from .schemas import Schemas
from .store import LoadedStore, load_store


@dataclass
class ValidationResult:
    errors: list[PlanError]
    store: LoadedStore
    graph: dict[str, Any] | None = None
    names: dict[str, dict[str, set[str]]] = field(default_factory=dict)
    # Each story's digest, review gate, and superseded story, by plan key.
    stories: dict[str, dict[str, Any]] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.errors


def validate(root: str | Path, *, show=openspec_show, schemas: Schemas | None = None,
             approvals: dict[str, str] | None = None, frozen: dict[str, str] | None = None) -> ValidationResult:
    """Validate the store at ``root``. Collects every problem; never stops at the first.

    ``approvals`` maps plan keys to the digests their approvals cover.
    ``frozen`` maps the plan keys of stories agents have started to their
    approved digests: such a story may not change or disappear."""
    root = Path(root).expanduser().resolve()
    schemas = schemas or Schemas.load(root)
    store = load_store(root, schemas)
    names_for = make_names_for(store, show=show)
    errors = list(store.errors) + check_graph(store, names_for) + check_frozen(store, frozen or {})
    if errors or store.plan is None:
        return ValidationResult(errors=errors, store=store)
    stories: dict[str, dict[str, Any]] = {}
    graph, errors = build_graph(store, names_for, schemas, approvals, stories)
    return ValidationResult(errors=errors, store=store, graph=graph, stories=stories)
