"""Sync through Sortie with a confirmed preview, and the per-change Approve action."""

from __future__ import annotations

import asyncio
import copy
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import planlib
from planlib import PlanLoadError

from .projects import ProjectManager
from .sortie import SortieError


class ApplyBody(BaseModel):
    preview_id: str
    confirm: bool = False


class ApproveBody(BaseModel):
    change: str


def sync_router(projects: ProjectManager, require_operator) -> APIRouter:
    router = APIRouter(prefix="/api/projects/{slug}", dependencies=[Depends(require_operator)])

    def sortie_failure(exc: SortieError) -> HTTPException:
        status = exc.status if exc.status >= 400 else 502
        return HTTPException(status_code=status, detail={"code": exc.code, "message": exc.message, **({"result": exc.body["result"]} if "result" in exc.body else {})})

    @router.post("/sync/preview")
    async def preview(slug: str) -> dict:
        rt = projects.get(slug)
        hub, pending = rt.hub, rt.pending
        snap = hub.plan.snapshot()
        if snap["errors"] or snap["graph"] is None:
            raise HTTPException(status_code=409, detail={"code": "plan_invalid", "message": "fix the plan's validation errors before syncing"})
        graph = copy.deepcopy(snap["graph"])
        try:
            body = await hub.sortie.preview(graph)
        except SortieError as exc:
            raise sortie_failure(exc) from exc
        missing = body["preview"].get("missing_capabilities") or []
        pending.clear()
        pending[body["preview_id"]] = {"graph": graph, "missing": missing}
        return {**body, "can_apply": not missing}

    @router.post("/sync/apply")
    async def apply(slug: str, body: ApplyBody) -> dict:
        rt = projects.get(slug)
        hub, pending = rt.hub, rt.pending
        if not body.confirm:
            raise HTTPException(status_code=400, detail={"code": "not_confirmed", "message": "confirm the preview to apply it"})
        held = pending.get(body.preview_id)
        if held is None:
            raise HTTPException(status_code=409, detail={"code": "stale_preview", "message": "request a new preview"})
        if held["missing"]:
            raise HTTPException(status_code=422, detail={
                "code": "tracker_unsupported_operation",
                "message": "the tracker lacks " + ", ".join(held["missing"]),
            })
        try:
            result = await hub.sortie.apply(held["graph"], body.preview_id)
        except SortieError as exc:
            raise sortie_failure(exc) from exc
        finally:
            pending.pop(body.preview_id, None)
            await hub.poll_once()
        return result

    @router.post("/approve")
    async def approve(slug: str, body: ApproveBody) -> dict:
        hub = projects.get(slug).hub
        snap = hub.plan.snapshot()
        blocking = [e for e in snap["errors"] if e.get("change") == body.change or e.get("change") is None]
        if blocking:
            raise HTTPException(status_code=409, detail={"code": "plan_invalid", "message": "fix the validation errors for this change first", "errors": blocking})
        try:
            digest = await asyncio.to_thread(planlib.approve, hub.plan.store, body.change)
        except PlanLoadError as exc:
            raise HTTPException(status_code=422, detail={"code": "cannot_approve", "message": str(exc)}) from exc
        await asyncio.to_thread(hub.plan.refresh)
        return {"change": body.change, "approved_digest": digest}

    return router
