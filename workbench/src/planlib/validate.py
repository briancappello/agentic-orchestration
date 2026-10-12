"""The validator's entry point: schema check, then graph checks, then the graph document."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .checks import check_graph, make_names_for
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

    @property
    def ok(self) -> bool:
        return not self.errors


def validate(root: str | Path, *, show=openspec_show, schemas: Schemas | None = None) -> ValidationResult:
    """Validate the store at ``root``. Collects every problem; never stops at the first."""
    root = Path(root).expanduser().resolve()
    schemas = schemas or Schemas.load(root)
    store = load_store(root, schemas)
    names_for = make_names_for(store, show=show)
    errors = list(store.errors) + check_graph(store, names_for)
    return ValidationResult(errors=errors, store=store)
