"""Keeps the merged graph current and fans it out to SSE subscribers."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from .merge import merge
from .plan_state import PlanState
from .sortie import SortieClient, SortieError

log = logging.getLogger(__name__)


class Hub:
    def __init__(self, plan: PlanState, sortie: SortieClient):
        self.plan = plan
        self.sortie = sortie
        self.tracker: dict[str, Any] | None = None
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
        try:
            graph = await self.sortie.plan_graph()
        except SortieError as exc:
            self.sortie_error = exc.message
            log.warning("sortie plan graph unavailable: %s", exc)
        else:
            self.tracker = graph
            self.capabilities = list(graph.get("capabilities") or [])
            self.sortie_error = None
        self.rebuild()

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
        self.version += 1
        doc.update(
            version=self.version,
            generated_at=time.time(),
            validation={"valid": snap["valid"], "errors": snap["errors"], "version": snap["version"]},
            sortie={
                "reachable": self.sortie_error is None and self.tracker is not None,
                "error": self.sortie_error,
                "capabilities": self.capabilities,
                "generated_at": (self.tracker or {}).get("generated_at"),
            },
        )
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
