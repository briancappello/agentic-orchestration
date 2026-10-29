"""The sync status of a project, and a retry for planners (workbench-auto-sync)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from .projects import ProjectManager


def sync_router(projects: ProjectManager, require_operator) -> APIRouter:
    router = APIRouter(prefix="/api/projects/{slug}", dependencies=[Depends(require_operator)])

    @router.get("/sync")
    def status(slug: str) -> dict:
        return projects.get(slug).sync.status()

    @router.post("/sync/retry")
    def retry(slug: str) -> dict:
        rt = projects.get(slug)
        rt.sync.trigger("retry")
        return rt.sync.status()

    return router
