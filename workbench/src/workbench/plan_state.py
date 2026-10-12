"""The store's plan as the validator reads it, kept current by a file watcher."""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Any, Callable

from watchfiles import awatch

import planlib
from planlib import PlanLoadError

log = logging.getLogger(__name__)

Validator = Callable[[Path], planlib.ValidationResult]


class PlanState:
    """The last valid plan graph and the current validation errors.

    An invalid store keeps the last valid graph and reports the errors, so
    the graph never disappears while someone fixes a file.
    """

    def __init__(self, store: Path, validate: Validator = planlib.validate):
        self.store = store
        self._validate = validate
        self.graph: dict[str, Any] | None = None
        self.errors: list[dict[str, Any]] = []
        self.version = 0
        self.validated_at = 0.0
        self._listeners: list[Callable[[], None]] = []

    def on_change(self, listener: Callable[[], None]) -> None:
        self._listeners.append(listener)

    def refresh(self) -> None:
        """Validate the store now and keep the result."""
        try:
            result = self._validate(self.store)
            errors = [e.to_dict() for e in result.errors]
            graph = result.graph
        except PlanLoadError as exc:
            errors = [{"code": "store", "message": str(exc), "file": None, "change": None, "deliverable": None, "members": []}]
            graph = None
        except Exception as exc:  # a validator crash must not stop the watcher
            log.exception("plan validation failed")
            errors = [{"code": "internal", "message": str(exc), "file": None, "change": None, "deliverable": None, "members": []}]
            graph = None
        if graph is not None:
            self.graph = graph
        self.errors = errors
        self.version += 1
        self.validated_at = time.time()
        for listener in list(self._listeners):
            listener()

    def snapshot(self) -> dict[str, Any]:
        return {"version": self.version, "valid": not self.errors, "errors": self.errors, "graph": self.graph}


async def watch(state: PlanState, debounce_ms: int, stop: asyncio.Event) -> None:
    """Re-validate whenever a file under the store's openspec/ changes."""
    root = state.store / "openspec"
    async for _changes in awatch(root, debounce=debounce_ms, step=50, stop_event=stop, recursive=True):
        await asyncio.to_thread(state.refresh)
