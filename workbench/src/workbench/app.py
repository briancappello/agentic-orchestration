"""The FastAPI application: sign-in, the plan graph, sync, approval, and planning sessions."""

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
from .hub import Hub, sse
from .plan_state import PlanState, watch
from .sortie import SortieClient
from .session_routes import session_router
from .sessions import SessionManager
from .sync import sync_router


_CODES = {401: "unauthorized", 404: "not_found"}


class LoginBody(BaseModel):
    password: str


def create_app(config: Config, **services) -> FastAPI:
    """Build the app. ``services`` lets tests inject collaborators:
    ``validate`` replaces planlib.validate and ``sortie`` the Sortie client."""
    plan_state = PlanState(config.store, **({"validate": services["validate"]} if "validate" in services else {}))
    sortie = services.get("sortie") or SortieClient(config.sortie_url, config.sortie_token)
    hub = Hub(plan_state, sortie)
    planning = services.get("sessions") or SessionManager(
        config.store, config.broker_command, config.agent_command, config.prompt_file
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        stop = asyncio.Event()
        hub.bind(asyncio.get_running_loop())
        await asyncio.to_thread(plan_state.refresh)
        tasks = [
            asyncio.create_task(watch(plan_state, config.debounce_ms, stop)),
            asyncio.create_task(hub.poll_loop(config.poll_seconds, stop)),
        ]
        try:
            yield
        finally:
            stop.set()
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            await sortie.aclose()
            await planning.aclose()

    app = FastAPI(title="plan workbench", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.state.plan = plan_state
    app.state.hub = hub
    app.state.sortie = sortie
    app.state.planning = planning
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

    @app.get("/api/graph", dependencies=[Depends(require_operator)])
    def graph() -> dict:
        return hub.doc

    @app.get("/api/events", dependencies=[Depends(require_operator)])
    async def events(request: Request) -> StreamingResponse:
        queue = hub.subscribe()

        async def stream():
            try:
                yield sse("graph", hub.doc)
                idle = 0.0
                while not await request.is_disconnected():
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

    app.include_router(sync_router(hub, require_operator))
    app.include_router(session_router(planning, require_operator))

    @app.exception_handler(HTTPException)
    async def http_error(_request: Request, exc: HTTPException) -> JSONResponse:
        detail = exc.detail if isinstance(exc.detail, dict) else {"code": _CODES.get(exc.status_code, "error"), "message": str(exc.detail)}
        return JSONResponse({"error": detail}, status_code=exc.status_code)

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
