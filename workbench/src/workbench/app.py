"""The FastAPI application: sign-in, projects, and each project's plan graph, sync, approval, and planning session."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .auth import COOKIE_NAME, Sessions, verify_password
from .config import Config
from .hub import sse
from .project_routes import project_router
from .projects import ProjectManager
from .registry import Registry, RegistryError
from .sortie import SortieClient
from .session_routes import session_router
from .sync import sync_router


_CODES = {401: "unauthorized", 404: "not_found"}


class LoginBody(BaseModel):
    password: str


def create_app(config: Config, **services) -> FastAPI:
    """Build the app. ``services`` lets tests inject collaborators:
    ``validate`` replaces planlib.validate, ``sortie`` the Sortie client, and
    ``sessions`` builds each project's session manager from
    ``(project, store, runtime_dir)``."""
    sortie = services.get("sortie") or SortieClient(config.sortie_url, config.sortie_token)
    registry = Registry(config.home / "workbench.db")
    projects = ProjectManager(config, registry, sortie, services.get("sessions"), services.get("validate"))

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await projects.start()
        try:
            yield
        finally:
            await projects.stop()
            await sortie.aclose()
            registry.close()

    app = FastAPI(title="plan workbench", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.state.projects = projects
    app.state.sortie = sortie
    sessions = Sessions(config.secret_key, config.session_max_age)
    app.state.config = config
    app.state.sessions = sessions
    app.state.services = services

    def require_operator(request: Request) -> None:
        if not sessions.valid(request.cookies.get(COOKIE_NAME)):
            raise HTTPException(status_code=401, detail="sign in first")

    app.state.require_operator = require_operator

    @app.post("/api/login")
    def login(body: LoginBody, response: Response) -> dict:
        if not verify_password(body.password, config.password_hash):
            raise HTTPException(status_code=401, detail="wrong password")
        response.set_cookie(
            COOKIE_NAME, sessions.issue(), max_age=config.session_max_age,
            httponly=True, samesite="strict", secure=config.cookie_secure, path="/",
        )
        return {"signed_in": True}

    @app.post("/api/logout")
    def logout(response: Response) -> dict:
        response.delete_cookie(COOKIE_NAME, path="/")
        return {"signed_in": False}

    @app.get("/api/me", dependencies=[Depends(require_operator)])
    def me() -> dict:
        return {"signed_in": True}

    app.include_router(project_router(projects, require_operator))

    @app.get("/api/projects/{slug}/validation", dependencies=[Depends(require_operator)])
    def validation(slug: str) -> dict:
        snap = projects.get(slug).plan.snapshot()
        return {"version": snap["version"], "valid": snap["valid"], "errors": snap["errors"], "has_graph": snap["graph"] is not None}

    @app.get("/api/projects/{slug}/graph", dependencies=[Depends(require_operator)])
    def graph(slug: str) -> dict:
        return projects.get(slug).hub.doc

    @app.get("/api/projects/{slug}/events", dependencies=[Depends(require_operator)])
    async def events(slug: str, request: Request) -> StreamingResponse:
        hub = projects.get(slug).hub
        queue = hub.subscribe()

        async def stream():
            try:
                yield sse("graph", hub.doc)
                idle = 0.0
                while not await request.is_disconnected():
                    if projects.runtimes.get(slug) is None:
                        yield sse("deleted", {"slug": slug})
                        return
                    try:
                        doc = await asyncio.wait_for(queue.get(), timeout=1)
                    except TimeoutError:
                        idle += 1
                        if idle >= 15:
                            idle = 0
                            yield ": keepalive\n\n"
                        continue
                    idle = 0
                    yield sse("graph", doc)
            finally:
                hub.unsubscribe(queue)

        return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-store"})

    app.include_router(sync_router(projects, require_operator))
    app.include_router(session_router(projects, require_operator))

    @app.exception_handler(RegistryError)
    async def registry_error(_request: Request, exc: RegistryError) -> JSONResponse:
        detail = {"code": exc.code, "message": exc.message, **({"field": exc.field} if exc.field else {})}
        return JSONResponse({"error": detail}, status_code=exc.status)

    @app.exception_handler(HTTPException)
    async def http_error(_request: Request, exc: HTTPException) -> JSONResponse:
        detail = exc.detail if isinstance(exc.detail, dict) else {"code": _CODES.get(exc.status_code, "error"), "message": str(exc.detail)}
        return JSONResponse({"error": detail}, status_code=exc.status_code)

    _mount_frontend(app, config.frontend_dir)
    return app


def create_app_from_env() -> FastAPI:
    """The app for ``uvicorn --factory``, configured from the environment."""
    return create_app(Config.from_env())


def _mount_frontend(app: FastAPI, dist: Path | None) -> None:
    if dist is None or not (dist / "index.html").is_file():
        return
    assets = dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        if path.startswith("api/"):
            raise HTTPException(status_code=404, detail="not found")
        candidate = (dist / path).resolve()
        if path and candidate.is_file() and dist.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(dist / "index.html")
