"""Keeps the merged graph current and fans it out to SSE subscribers."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from .merge import merge
from .plan_overlay import frozen_set, overlay
from .plan_state import PlanState
from .sortie import ProjectSortie, SortieError
from .workers import worker_fields

log = logging.getLogger(__name__)


class Hub:
    def __init__(self, plan: PlanState, sortie: ProjectSortie, records=None):
        self.plan = plan
        self.sortie = sortie
        # (approvals, rereviews) of the project, by plan key.
        self.records = records or (lambda: ({}, {}))
        self.frozen: dict[str, str] = {}
        self.fields: dict[str, dict[str, Any]] = {}
        self._pulled_back: set[str] = set()
        self.tracker: dict[str, Any] | None = None
        # Worker fields by tracker identifier, from Sortie's state.
        self.workers: dict[str, dict[str, Any]] = {}
        self.sortie_error: str | None = None
        self.capabilities: list[str] = []
        self.version = 0
        self.doc: dict[str, Any] = {}
        self._subscribers: set[asyncio.Queue] = set()
        self._loop: asyncio.AbstractEventLoop | None = None
        plan.on_change(self.rebuild)

    def bind(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    async def poll_once(self) -> None:
        # Catch store edits the file watcher missed.
        if await asyncio.to_thread(self.plan.stale):
            await asyncio.to_thread(self.plan.refresh)
        try:
            graph = await self.sortie.plan_graph()
        except SortieError as exc:
            self.sortie_error = exc.message
            log.warning("sortie plan graph unavailable: %s", exc)
        else:
            self.tracker = graph
            self.capabilities = list(graph.get("capabilities") or [])
            self.sortie_error = None
            self.workers = await self._workers(graph)
            approvals, _ = self.records()
            frozen = frozen_set(self.plan.stories, approvals, graph)
            if frozen != self.frozen:
                self.frozen = frozen
                # Edits to stories that just started are now refused.
                await asyncio.to_thread(self.plan.refresh)
                return
        self.rebuild()
        await self.pull_back_stale()

    async def _workers(self, graph: dict[str, Any]) -> dict[str, dict[str, Any]]:
        if not graph.get("dispatched") or not any(n.get("runtime") for n in graph.get("nodes") or []):
            return {}
        try:
            return worker_fields(await self.sortie.state())
        except SortieError as exc:
            log.warning("sortie state unavailable: %s", exc)
            return {}

    async def pull_back_stale(self) -> None:
        """Pull back each released story whose content changed since its
        approval, before an agent takes the old content."""
        # A story pulled back and released again may need pulling back again.
        self._pulled_back = {k for k in self._pulled_back if self.fields.get(k, {}).get("stale_release")}
        for key, f in list(self.fields.items()):
            if not f.get("stale_release") or key in self._pulled_back:
                continue
            self._pulled_back.add(key)
            try:
                await self.sortie.pull_back(key)
                log.info("pulled back %s: its content changed after its release", key)
            except SortieError as exc:
                log.warning("could not pull back edited story %s: %s", key, exc.message)

    async def poll_loop(self, interval: float, stop: asyncio.Event) -> None:
        while not stop.is_set():
            await self.poll_once()
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval)
            except TimeoutError:
                pass

    def rebuild(self) -> None:
        snap = self.plan.snapshot()
        doc = merge(snap["graph"], self.tracker)
        approvals, rereviews = self.records()
        self.fields = overlay(snap["graph"], self.plan.stories, approvals, rereviews, self.tracker)
        for n in doc["nodes"]:
            n.update(self.fields.get(n["plan_key"], {}))
            if n.get("runtime") and n.get("tracker"):
                n["runtime"] = {"stage": None, "session_id": None, "held": False, "holder": None, "watchable": False,
                                **n["runtime"], **self.workers.get(n["tracker"]["identifier"], {})}
        self.version += 1
        doc.update(
            version=self.version,
            generated_at=time.time(),
            validation={"valid": snap["valid"], "errors": snap["errors"], "version": snap["version"]},
            sortie={
                "reachable": self.sortie_error is None and self.tracker is not None,
                "error": self.sortie_error,
                "capabilities": self.capabilities,
                "project": self.sortie.project,
                # Sortie runs agents for its configured project only.
                "dispatched": bool((self.tracker or {}).get("dispatched", False)),
                "generated_at": (self.tracker or {}).get("generated_at"),
            },
        )
        doc["plan_states"] = (self.tracker or {}).get("plan_states")
        self.doc = doc
        self._publish(doc)

    def _publish(self, doc: dict[str, Any]) -> None:
        if self._loop is None:
            return
        for q in list(self._subscribers):
            self._loop.call_soon_threadsafe(_offer, q, doc)

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=8)
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subscribers.discard(q)


def _offer(q: asyncio.Queue, doc: dict[str, Any]) -> None:
    # A slow subscriber only needs the newest graph.
    while q.full():
        q.get_nowait()
    q.put_nowait(doc)


def sse(event: str, data: Any) -> str:
    return f"event: {event}\ndata: {json.dumps(data, separators=(',', ':'))}\n\n"
