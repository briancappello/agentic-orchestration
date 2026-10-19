"""Project CRUD: list, create, read, rename, delete."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from .projects import ProjectManager
from .registry import suggest_slug
from .sortie import SortieError


class CreateBody(BaseModel):
    name: str
    slug: str = ""
    huly_project: str


class RenameBody(BaseModel):
    name: str


def project_router(projects: ProjectManager, require_operator) -> APIRouter:
    router = APIRouter(prefix="/api/projects", dependencies=[Depends(require_operator)])

    @router.get("")
    def list_projects() -> dict:
        return {"projects": [projects.runtimes[p.slug].summary() for p in projects.registry.list() if p.slug in projects.runtimes]}

    @router.post("", status_code=201)
    async def create(body: CreateBody) -> dict:
        rt, tracker = await projects.create(body.slug or suggest_slug(body.name), body.name, body.huly_project)
        return {"project": rt.summary(), "tracker": tracker}

    @router.get("/{slug}")
    async def read(slug: str) -> dict:
        rt = projects.get(slug)
        try:
            tracker = await projects.sortie.project(rt.project.huly_project)
            tracker_error = None
        except SortieError as exc:
            tracker, tracker_error = None, exc.message
        return {"project": rt.summary(), "tracker": tracker, "tracker_error": tracker_error}

    @router.patch("/{slug}")
    def rename(slug: str, body: RenameBody) -> dict:
        return {"project": projects.rename(slug, body.name).summary()}

    @router.delete("/{slug}")
    async def delete(slug: str) -> dict:
        return await projects.delete(slug)

    return router
