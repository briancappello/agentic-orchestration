"""Sync through Sortie with a confirmed preview."""

from __future__ import annotations

import copy
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .plan_overlay import sync_graph
from .projects import ProjectManager
from .sortie import SortieError


class ApplyBody(BaseModel):
    preview_id: str
    confirm: bool = False


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
        graph = sync_graph(copy.deepcopy(snap["graph"]), hub.fields)
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

    return router
