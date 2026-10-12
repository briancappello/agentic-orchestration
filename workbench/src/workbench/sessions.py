"""Planning sessions that outlive the backend.

Each session is one ``acp-broker`` driven by a detached
``workbench.session_driver`` process (see that module for why it is a
separate process). The backend keeps nothing about the session in memory:
the session's state lives in a runtime directory, one per spec store, so a
restarted or reloaded backend finds the running session again and relays
it. Only "End session" stops it.

The broker's viewer token stays on the server. The browser only ever holds
the workbench cookie.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import secrets
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, AsyncIterator

import httpx

log = logging.getLogger(__name__)


class SessionError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def default_runtime_dir(store: Path) -> Path:
    """A per-store directory that survives backend restarts: under
    ``$XDG_RUNTIME_DIR`` when set, else under ``~/.cache``."""
    base = os.environ.get("XDG_RUNTIME_DIR") or str(Path.home() / ".cache")
    digest = hashlib.sha256(str(store.resolve()).encode()).hexdigest()[:12]
    return Path(base) / "plan-workbench" / f"{store.name}-{digest}"


def _alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


class SessionManager:
    def __init__(
        self,
        store: Path,
        broker_command: list[str],
        agent_command: list[str],
        prompt_file: Path | None,
        runtime_dir: Path | None = None,
        start_timeout: float = 20.0,
    ):
        self.store = Path(store)
        self.broker_command = broker_command
        self.agent_command = agent_command
        self.prompt_file = prompt_file
        self.runtime_dir = runtime_dir or default_runtime_dir(self.store)
        self.runtime_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.runtime_dir, 0o700)
        self.start_timeout = start_timeout
        self._lock = asyncio.Lock()
        self._http = httpx.AsyncClient(timeout=httpx.Timeout(30.0, read=None))
        # The driver this process started, kept so its exit is reaped.
        self._child: subprocess.Popen | None = None

    async def aclose(self) -> None:
        """Release the backend's resources. The session keeps running."""
        await self._http.aclose()

    # State in the runtime directory.

    @property
    def _state_path(self) -> Path:
        return self.runtime_dir / "state.json"

    def _state(self) -> dict[str, Any] | None:
        try:
            return json.loads(self._state_path.read_text())
        except (OSError, ValueError):
            return None

    def _live_state(self) -> dict[str, Any] | None:
        """The running session's state, or None when no session runs."""
        if self._child is not None:
            self._child.poll()
        st = self._state()
        if not st or st.get("ended_at") or not _alive(st.get("driver_pid")) or not _alive(st.get("broker_pid")):
            return None
        return st

    def _messages_path(self, key: str) -> Path:
        return self.runtime_dir / f"{key}.messages.jsonl"

    def _messages(self, key: str) -> list[dict[str, Any]]:
        try:
            lines = self._messages_path(key).read_text().splitlines()
        except OSError:
            return []
        out = []
        for line in lines:
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
        return out

    def status(self) -> dict[str, Any]:
        st = self._live_state()
        if st is None:
            last = self._state()
            return {"active": False, "error": last.get("error") if last else None}
        return {
            "active": True,
            "key": st["key"],
            "acp_session_id": st.get("acp_session_id"),
            "started_at": st.get("started_at"),
            "error": st.get("error"),
            "messages": self._messages(st["key"]),
        }

    # Lifecycle.

    async def start(self) -> dict[str, Any]:
        async with self._lock:
            if self._live_state():
                return self.status()
            self._cleanup_ended()
            key = "planning-" + secrets.token_hex(4)
            spec = {
                "key": key,
                "store": str(self.store),
                "broker_command": self.broker_command,
                "agent_command": self.agent_command,
                "prompt": self._planning_prompt(),
            }
            (self.runtime_dir / "spec.json").write_text(json.dumps(spec))
            self._state_path.unlink(missing_ok=True)
            env = {k: v for k, v in os.environ.items() if not k.startswith(("SORTIE_", "WORKBENCH_"))}
            src = Path(__file__).resolve().parents[1]
            env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(src), env.get("PYTHONPATH", "")]))
            self._child = subprocess.Popen(
                [sys.executable, "-m", "workbench.session_driver", str(self.runtime_dir)],
                cwd=self.store, env=env, start_new_session=True,
                stdin=subprocess.DEVNULL,
                stdout=open(self.runtime_dir / "driver.log", "ab"),  # noqa: SIM115
                stderr=subprocess.STDOUT,
            )
            await self._wait_ready()
            log.info("planning session %s started; runtime directory %s", key, self.runtime_dir)
            return self.status()

    async def _wait_ready(self) -> None:
        deadline = time.monotonic() + self.start_timeout
        while time.monotonic() < deadline:
            st = self._state()
            if st and st.get("http_url"):
                return
            if self._child is not None and self._child.poll() is not None:
                err = (st or {}).get("error") or f"the session driver exited with code {self._child.returncode}"
                raise SessionError(502, "broker_exited", err)
            if st and st.get("ended_at"):
                raise SessionError(502, "broker_exited", st.get("error") or "the session ended while starting")
            await asyncio.sleep(0.05)
        await self._terminate()
        raise SessionError(504, "broker_timeout", "acp-broker did not register in time")

    async def stop(self) -> dict[str, Any]:
        async with self._lock:
            await self._terminate()
            return {"active": False}

    async def _terminate(self) -> None:
        st = self._state()
        pid = (st or {}).get("driver_pid") or (self._child.pid if self._child else None)
        if pid and _alive(pid):
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                if self._child is not None and self._child.pid == pid:
                    if self._child.poll() is not None:
                        break
                elif not _alive(pid):
                    break
                await asyncio.sleep(0.05)
            else:
                os.kill(pid, signal.SIGKILL)
        broker = (st or {}).get("broker_pid")
        if broker and _alive(broker):  # the driver died without stopping it
            os.kill(broker, signal.SIGTERM)
        self._child = None

    def _cleanup_ended(self) -> None:
        """Remove what an ended session left: its token, messages, and logs."""
        st = self._state()
        if not st:
            return
        for suffix in (".token", ".messages.jsonl", ".stderr"):
            (self.runtime_dir / f"{st['key']}{suffix}").unlink(missing_ok=True)
        shutil.rmtree(self.runtime_dir / "registry", ignore_errors=True)

    def _planning_prompt(self) -> str:
        if self.prompt_file is None or not self.prompt_file.is_file():
            return ""
        return self.prompt_file.read_text().replace("{{store}}", str(self.store))

    # The viewer side, relayed to the browser.

    def _require(self) -> tuple[dict[str, Any], str]:
        st = self._live_state()
        if st is None or not st.get("http_url"):
            raise SessionError(409, "no_session", "start a planning session first")
        token = Path(st["token_file"]).read_text().strip()
        return st, token

    async def command(self, cmd: dict[str, Any]) -> tuple[int, Any]:
        """Send one viewer command. The broker's events carry no human
        messages, so the text of accepted steers and prompts is kept in the
        runtime directory for a reloaded chat to show."""
        st, token = self._require()
        r = await self._http.post(f"{st['http_url']}/commands", json=cmd, headers={"Authorization": f"Bearer {token}"})
        if r.status_code == 200 and cmd.get("op") in ("steer", "prompt") and isinstance(cmd.get("text"), str):
            with self._messages_path(st["key"]).open("a") as f:
                f.write(json.dumps({"time": time.time(), "op": cmd["op"], "text": cmd["text"]}) + "\n")
        try:
            body = r.json()
        except ValueError:
            body = {"error": r.text}
        return r.status_code, body

    async def events(self, last_event_id: str | None) -> AsyncIterator[bytes]:
        st, token = self._require()
        headers = {"Authorization": f"Bearer {token}", "Accept": "text/event-stream"}
        if last_event_id:
            headers["Last-Event-ID"] = last_event_id
        async with self._http.stream("GET", f"{st['http_url']}/events", headers=headers) as r:
            if r.status_code != 200:
                raise SessionError(502, "broker_error", f"acp-broker answered {r.status_code}")
            async for chunk in r.aiter_raw():
                yield chunk
