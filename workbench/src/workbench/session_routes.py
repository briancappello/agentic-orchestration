"""HTTP routes that relay the planning session under the operator cookie."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from .projects import ProjectManager
from .sessions import SessionError

# The broker commands a person may send from the chat pane.
ALLOWED_OPS = {"steer", "prompt", "permit", "interrupt", "handback", "state"}


def session_router(projects: ProjectManager, require_operator) -> APIRouter:
    """The planning session of each project, under /api/projects/{slug}/session."""
    router = APIRouter(prefix="/api/projects/{slug}/session", dependencies=[Depends(require_operator)])

    def fail(exc: SessionError) -> HTTPException:
        return HTTPException(status_code=exc.status, detail={"code": exc.code, "message": exc.message})

    @router.get("")
    def status(slug: str) -> dict:
        manager = projects.get(slug).sessions
        return manager.status()

    @router.post("")
    async def start(slug: str, body: dict[str, Any] | None = None) -> dict:
        manager = projects.get(slug).sessions
        try:
            return await manager.start((body or {}).get("message"))
        except SessionError as exc:
            raise fail(exc) from exc

    @router.delete("")
    async def stop(slug: str) -> dict:
        manager = projects.get(slug).sessions
        return await manager.stop()

    @router.get("/config")
    def config(slug: str) -> dict:
        manager = projects.get(slug).sessions
        try:
            return manager.config()
        except SessionError as exc:
            raise fail(exc) from exc

    @router.put("/config")
    async def set_config(slug: str, change: dict[str, Any]) -> dict:
        manager = projects.get(slug).sessions
        try:
            return await manager.set_config(change.get("category"), change.get("value"))
        except SessionError as exc:
            raise fail(exc) from exc

    @router.post("/commands")
    async def command(slug: str, cmd: dict[str, Any]) -> JSONResponse:
        manager = projects.get(slug).sessions
        if cmd.get("op") not in ALLOWED_OPS:
            raise HTTPException(status_code=400, detail={"code": "invalid_command", "message": f"op must be one of {sorted(ALLOWED_OPS)}"})
        try:
            code, body = await manager.command(cmd)
        except SessionError as exc:
            raise fail(exc) from exc
        return JSONResponse(body, status_code=code)

    @router.get("/events")
    async def events(slug: str, request: Request) -> StreamingResponse:
        manager = projects.get(slug).sessions
        try:
            stream = manager.events(request.headers.get("last-event-id") or request.query_params.get("last_event_id"))
            first = await anext(stream)
        except SessionError as exc:
            raise fail(exc) from exc
        except StopAsyncIteration:
            first = b""

        async def relay():
            yield first
            async for chunk in stream:
                if await request.is_disconnected():
                    break
                yield chunk

        return StreamingResponse(relay(), media_type="text/event-stream", headers={"Cache-Control": "no-store"})

    return router
