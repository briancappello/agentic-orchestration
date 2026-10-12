"""The FastAPI application: sign-in, the plan graph, sync, approval, and planning sessions."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .auth import COOKIE_NAME, Sessions, verify_password
from .config import Config
from .plan_state import PlanState, watch


class LoginBody(BaseModel):
    password: str


def create_app(config: Config, **services) -> FastAPI:
    """Build the app. ``services`` lets tests inject collaborators:
    ``validate`` replaces planlib.validate."""
    plan_state = PlanState(config.store, **({"validate": services["validate"]} if "validate" in services else {}))

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        stop = asyncio.Event()
        await asyncio.to_thread(plan_state.refresh)
        tasks = [asyncio.create_task(watch(plan_state, config.debounce_ms, stop))]
        try:
            yield
        finally:
            stop.set()
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    app = FastAPI(title="plan workbench", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.state.plan = plan_state
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
        return {"signed_in": True, "store": config.store.name}

    @app.get("/api/validation", dependencies=[Depends(require_operator)])
    def validation() -> dict:
        snap = plan_state.snapshot()
        return {"version": snap["version"], "valid": snap["valid"], "errors": snap["errors"], "has_graph": snap["graph"] is not None}

    @app.exception_handler(HTTPException)
    async def http_error(_request: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse({"error": exc.detail}, status_code=exc.status_code)

    _mount_frontend(app, config.frontend_dir)
    return app


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
