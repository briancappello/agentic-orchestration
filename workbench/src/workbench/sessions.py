"""Planning sessions: one standalone acp-broker per session, relayed to the browser.

The backend is the session's ACP client. It starts the broker with the
spec store as the working directory, opens an ACP session, and sends the
planning prompt as the first turn. People then talk to the agent through
the broker's viewer transport: their messages are steers, which run as
turns of their own when the agent is idle, and their permission answers
are permits. The broker's viewer token stays in this process; the browser
only ever holds the workbench cookie.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import secrets
import socket
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator

import httpx

log = logging.getLogger(__name__)

ACP_PROTOCOL_VERSION = 1


class SessionError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


@dataclass
class PlanningSession:
    key: str
    process: asyncio.subprocess.Process
    http_url: str
    token: str
    workdir: Path
    started_at: float
    acp_session_id: str | None = None
    driver: asyncio.Task | None = None
    driver_error: str | None = None
    _next_id: int = 0
    _waiting: dict[int, asyncio.Future] = field(default_factory=dict)

    def status(self) -> dict[str, Any]:
        return {
            "active": self.process.returncode is None,
            "key": self.key,
            "acp_session_id": self.acp_session_id,
            "started_at": self.started_at,
            "error": self.driver_error,
        }


class SessionManager:
    def __init__(
        self,
        store: Path,
        broker_command: list[str],
        agent_command: list[str],
        prompt_file: Path | None,
        runtime_dir: Path | None = None,
        start_timeout: float = 15.0,
    ):
        self.store = store
        self.broker_command = broker_command
        self.agent_command = agent_command
        self.prompt_file = prompt_file
        self.runtime_dir = runtime_dir or Path(tempfile.mkdtemp(prefix="workbench-broker-"))
        self.runtime_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.runtime_dir, 0o700)
        self.start_timeout = start_timeout
        self.session: PlanningSession | None = None
        self._lock = asyncio.Lock()
        self._http = httpx.AsyncClient(timeout=httpx.Timeout(30.0, read=None))

    async def aclose(self) -> None:
        await self.stop()
        await self._http.aclose()

    def status(self) -> dict[str, Any]:
        if self.session is None:
            return {"active": False}
        return self.session.status()

    async def start(self) -> dict[str, Any]:
        async with self._lock:
            if self.session and self.session.process.returncode is None:
                return self.session.status()
            self.session = None
            key = "planning-" + secrets.token_hex(4)
            token = secrets.token_urlsafe(32)
            token_file = self.runtime_dir / f"{key}.token"
            token_file.write_text(token)
            os.chmod(token_file, 0o600)
            port = _free_port()
            argv = [
                *self.broker_command,
                "-key", key,
                "-registry-dir", str(self.runtime_dir / "registry"),
                "-http", f"127.0.0.1:{port}",
                "-viewer-token-file", str(token_file),
                "-handback-grace", "24h",
                "--", *self.agent_command,
            ]
            env = {k: v for k, v in os.environ.items() if not k.startswith("SORTIE_") and not k.startswith("WORKBENCH_")}
            process = await asyncio.create_subprocess_exec(
                *argv, cwd=self.store, env=env,
                stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                stderr=open(self.runtime_dir / f"{key}.stderr", "wb"),  # noqa: SIM115
            )
            try:
                http_url = await self._find_record(key, process)
            except Exception:
                process.kill()
                await process.wait()
                raise
            session = PlanningSession(key=key, process=process, http_url=http_url, token=token,
                                      workdir=self.store, started_at=time.time())
            self.session = session
            session.driver = asyncio.create_task(self._drive(session))
            return session.status()

    async def stop(self) -> dict[str, Any]:
        async with self._lock:
            session, self.session = self.session, None
            if session is None:
                return {"active": False}
            if session.process.stdin and not session.process.stdin.is_closing():
                session.process.stdin.close()
            if session.process.returncode is None:
                session.process.terminate()
                try:
                    await asyncio.wait_for(session.process.wait(), timeout=10)
                except TimeoutError:
                    session.process.kill()
                    await session.process.wait()
            if session.driver:
                session.driver.cancel()
            return {"active": False}

    async def _find_record(self, key: str, process: asyncio.subprocess.Process) -> str:
        """Find the broker through its registry record and wait for its HTTP listener."""
        deadline = time.monotonic() + self.start_timeout
        registry = self.runtime_dir / "registry"
        while time.monotonic() < deadline:
            if process.returncode is not None:
                raise SessionError(502, "broker_exited", f"acp-broker exited with code {process.returncode}")
            for rec_path in registry.glob(f"{key}.*.json"):
                try:
                    rec = json.loads(rec_path.read_text())
                except (OSError, ValueError):
                    continue
                if rec.get("key") == key and rec.get("pid") == process.pid and rec.get("http_url"):
                    return rec["http_url"].rstrip("/")
            await asyncio.sleep(0.05)
        raise SessionError(504, "broker_timeout", "acp-broker did not register in time")

    def _require(self) -> PlanningSession:
        if self.session is None or self.session.process.returncode is not None:
            raise SessionError(409, "no_session", "start a planning session first")
        return self.session

    # The ACP client side, on the broker's standard input and output.

    async def _drive(self, s: PlanningSession) -> None:
        reader = asyncio.create_task(self._read(s))
        try:
            await self._call(s, "initialize", {
                "protocolVersion": ACP_PROTOCOL_VERSION,
                "clientCapabilities": {"fs": {"readTextFile": False, "writeTextFile": False}, "terminal": False},
                "clientInfo": {"name": "plan-workbench", "version": "0.1.0"},
            })
            new = await self._call(s, "session/new", {"cwd": str(s.workdir), "mcpServers": []})
            s.acp_session_id = new.get("sessionId")
            prompt = self._planning_prompt()
            if prompt:
                await self._call(s, "session/prompt", {
                    "sessionId": s.acp_session_id, "prompt": [{"type": "text", "text": prompt}],
                })
            await reader
        except asyncio.CancelledError:
            reader.cancel()
            raise
        except Exception as exc:  # reported in the session status
            s.driver_error = str(exc)
            log.warning("planning session driver stopped: %s", exc)
            reader.cancel()

    def _planning_prompt(self) -> str:
        if self.prompt_file is None or not self.prompt_file.is_file():
            return ""
        return self.prompt_file.read_text().replace("{{store}}", str(self.store))

    async def _call(self, s: PlanningSession, method: str, params: dict[str, Any]) -> dict[str, Any]:
        s._next_id += 1
        msg_id = s._next_id
        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        s._waiting[msg_id] = fut
        await self._send(s, {"jsonrpc": "2.0", "id": msg_id, "method": method, "params": params})
        reply = await fut
        if "error" in reply:
            raise SessionError(502, "acp_error", f"{method}: {reply['error'].get('message')}")
        return reply.get("result") or {}

    async def _send(self, s: PlanningSession, msg: dict[str, Any]) -> None:
        assert s.process.stdin is not None
        s.process.stdin.write((json.dumps(msg) + "\n").encode())
        await s.process.stdin.drain()

    async def _read(self, s: PlanningSession) -> None:
        assert s.process.stdout is not None
        while line := await s.process.stdout.readline():
            try:
                msg = json.loads(line)
            except ValueError:
                continue
            if "method" not in msg and msg.get("id") in s._waiting:
                s._waiting.pop(msg["id"]).set_result(msg)
            elif "method" in msg and "id" in msg:
                await self._answer(s, msg)

    async def _answer(self, s: PlanningSession, msg: dict[str, Any]) -> None:
        # A permission request reaches the driver only after viewers had
        # their chance; the workbench never grants on a person's behalf.
        if msg["method"] == "session/request_permission":
            result = {"outcome": {"outcome": "cancelled"}}
            await self._send(s, {"jsonrpc": "2.0", "id": msg["id"], "result": result})
        else:
            await self._send(s, {"jsonrpc": "2.0", "id": msg["id"],
                                 "error": {"code": -32601, "message": f"{msg['method']} is not supported by the workbench"}})

    # The viewer side, relayed to the browser.

    async def command(self, cmd: dict[str, Any]) -> tuple[int, Any]:
        s = self._require()
        r = await self._http.post(f"{s.http_url}/commands", json=cmd, headers={"Authorization": f"Bearer {s.token}"})
        try:
            body = r.json()
        except ValueError:
            body = {"error": r.text}
        return r.status_code, body

    async def events(self, last_event_id: str | None) -> AsyncIterator[bytes]:
        s = self._require()
        headers = {"Authorization": f"Bearer {s.token}", "Accept": "text/event-stream"}
        if last_event_id:
            headers["Last-Event-ID"] = last_event_id
        async with self._http.stream("GET", f"{s.http_url}/events", headers=headers) as r:
            if r.status_code != 200:
                raise SessionError(502, "broker_error", f"acp-broker answered {r.status_code}")
            async for chunk in r.aiter_raw():
                yield chunk


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]
