"""HTTP routes that let a person watch and steer the workers Sortie runs for
a project's stories, under /api/projects/{slug}/workers/{identifier}."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from .auth import APPROVER, PLANNER, Identity
from .projects import ProjectManager, ProjectRuntime
from .session_routes import ALLOWED_OPS
from .workers import WorkerError

log = logging.getLogger(__name__)

# What a planner may send: it reads, and changes nothing an agent does.
READ_OPS = {"state"}


def worker_router(projects: ProjectManager, require_role) -> APIRouter:
    router = APIRouter(prefix="/api/projects/{slug}/workers/{identifier}")
    planner = require_role(PLANNER)

    def story(rt: ProjectRuntime, identifier: str) -> dict[str, Any]:
        """The story whose tracker issue is ``identifier``; 404 for any other,
        before anything reaches Sortie."""
        for n in rt.hub.doc.get("nodes") or []:
            if n.get("kind") == "story" and (n.get("tracker") or {}).get("identifier") == identifier:
                return n
        raise HTTPException(status_code=404, detail={"code": "worker_not_found", "message": f"{identifier} is not a story of this project"})

    def fail(exc: WorkerError) -> HTTPException:
        return HTTPException(status_code=exc.status, detail={"code": exc.code, "message": exc.message})

    @router.get("/messages")
    def messages(slug: str, identifier: str, _who: Identity = Depends(planner)) -> dict:
        rt = projects.get(slug)
        story(rt, identifier)
        rows = rt.registry.commands(rt.project.id, identifier) if rt.registry else []
        return {"identifier": identifier, "commands": rows}

    @router.post("/commands")
    async def command(slug: str, identifier: str, cmd: dict[str, Any], who: Identity = Depends(planner)) -> JSONResponse:
        rt = projects.get(slug)
        node = story(rt, identifier)
        op = cmd.get("op")
        if op not in ALLOWED_OPS:
            raise HTTPException(status_code=400, detail={"code": "invalid_command", "message": f"op must be one of {sorted(ALLOWED_OPS)}"})
        if op not in READ_OPS and not who.has(APPROVER):
            raise HTTPException(status_code=403, detail={"code": "role_required", "message": "steering a worker needs the approver role"})
        try:
            code, body, run = await rt.workers.command(identifier, cmd)
        except WorkerError as exc:
            raise fail(exc) from exc
        if 200 <= code < 300 and op not in READ_OPS and rt.registry is not None:
            text = cmd.get("text") if isinstance(cmd.get("text"), str) else None
            if op == "permit":
                text = str(cmd.get("option") or "")
            rec = await asyncio.to_thread(rt.registry.record_command, rt.project.id, identifier, run, op, text, who.key, who.name)
            log.info("project %s: %s sent %s to %s (%s)", slug, who.key, op, identifier, node["plan_key"])
            body = {**body, "recorded": rec} if isinstance(body, dict) else {"result": body, "recorded": rec}
        return JSONResponse(body, status_code=code)

    @router.get("/events")
    async def events(slug: str, identifier: str, request: Request, _who: Identity = Depends(planner)) -> StreamingResponse:
        rt = projects.get(slug)
        story(rt, identifier)

        async def connected() -> bool:
            return not await request.is_disconnected()

        last = request.headers.get("last-event-id") or request.query_params.get("last_event_id")
        stream = rt.workers.events(identifier, last, connected)

        async def relay():
            try:
                async for chunk in stream:
                    yield chunk
            except WorkerError as exc:
                log.warning("worker %s stream failed: %s", identifier, exc.message)

        return StreamingResponse(relay(), media_type="text/event-stream", headers={"Cache-Control": "no-store"})

    return router
