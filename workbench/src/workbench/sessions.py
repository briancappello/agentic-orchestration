"""Planning sessions that outlive the backend.

Each session is one ``acp-broker`` driven by a detached
``workbench.session_driver`` process (see that module for why it is a
separate process). The backend keeps nothing about the session in memory:
the session's state lives in a runtime directory, one per project, so a
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

from planlib.requirements import OPENSPEC_ENV

log = logging.getLogger(__name__)

MODEL_CATEGORY = "model"
CONFIG_CATEGORIES = (MODEL_CATEGORY, "thought_level")


def write_json_atomic(path: Path, data: dict[str, Any]) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data))
    os.replace(tmp, path)


class SessionError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def runtime_base() -> Path:
    """The parent of the projects' runtime directories when none is configured:
    under ``$XDG_RUNTIME_DIR`` when set, else under ``~/.cache``."""
    return Path(os.environ.get("XDG_RUNTIME_DIR") or str(Path.home() / ".cache")) / "plan-workbench"


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
        agent_model: str = "",
    ):
        self.store = Path(store)
        self.broker_command = broker_command
        self.agent_command = agent_command
        self.agent_model = agent_model
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
            "can_configure": bool(st.get("can_configure")),
            "model": st.get("model"),
            "thought_level": st.get("thought_level"),
            "started_at": st.get("started_at"),
            "error": st.get("error"),
            "messages": self._messages(st["key"]),
        }

    # Lifecycle.

    async def start(self, message: str) -> dict[str, Any]:
        """Start a session whose first turn is the person's first message.

        The agent does nothing before the person says what to plan: the
        planning instructions travel with that message, in the same turn.
        """
        if not isinstance(message, str) or not message.strip():
            raise SessionError(400, "message_required", "a session starts with the person's first message")
        async with self._lock:
            if self._live_state():
                raise SessionError(409, "session_running", "a planning session is already running; send the message to it")
            self._cleanup_ended()
            key = "planning-" + secrets.token_hex(4)
            spec = {
                "key": key,
                "store": str(self.store),
                "broker_command": self.broker_command,
                "agent_command": self.agent_command,
                "model": self.agent_model,
                "preferred": self._preferences(),
                "prompt": self._planning_prompt(),
                "message": message,
            }
            (self.runtime_dir / "spec.json").write_text(json.dumps(spec))
            # The broker's events carry no human messages: keep this one for the chat to show.
            with self._messages_path(key).open("a") as f:
                f.write(json.dumps({"time": time.time(), "op": "prompt", "text": message}) + "\n")
            self._state_path.unlink(missing_ok=True)
            env = {k: v for k, v in os.environ.items() if not k.startswith(("SORTIE_", "WORKBENCH_"))}
            # The planning agent runs openspec too: no usage telemetry from it either.
            env = {**OPENSPEC_ENV, **env}
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
        (self.runtime_dir / "config.json").unlink(missing_ok=True)
        shutil.rmtree(self.runtime_dir / "registry", ignore_errors=True)

    def _planning_prompt(self) -> str:
        if self.prompt_file is None or not self.prompt_file.is_file():
            return ""
        return self.prompt_file.read_text().replace("{{store}}", str(self.store))

    # Model and thinking level. ACP lets only the client set config options,
    # so the change goes to the driver, which holds the client side.

    def _preferences(self) -> dict[str, str]:
        try:
            prefs = json.loads((self.runtime_dir / "preferences.json").read_text())
        except (OSError, ValueError):
            return {}
        return {k: v for k, v in prefs.items() if k in CONFIG_CATEGORIES and isinstance(v, str)} if isinstance(prefs, dict) else {}

    def _require_configurable(self) -> None:
        st, _ = self._require()
        if not st.get("can_configure"):
            raise SessionError(409, "not_configurable",
                               "this session was started before model choice existed; end it to choose a model")

    def config(self) -> dict[str, Any]:
        """The running session's choosable config options, with their current values."""
        self._require_configurable()
        try:
            return json.loads((self.runtime_dir / "config.json").read_text())
        except (OSError, ValueError):
            return {"options": [], "ready": False}

    async def set_config(self, category: str, value: str) -> dict[str, Any]:
        """Change the model or thinking level, and remember it for the next session."""
        if category not in CONFIG_CATEGORIES or not isinstance(value, str) or not value:
            raise SessionError(400, "invalid_config", "category must be model or thought_level, with a value")
        self._require_configurable()
        try:
            reader, writer = await asyncio.open_unix_connection(str(self.runtime_dir / "ctl.sock"))
        except OSError as exc:
            raise SessionError(502, "driver_unavailable", "the session driver does not answer") from exc
        try:
            writer.write((json.dumps({"category": category, "value": value}) + "\n").encode())
            await writer.drain()
            reply = json.loads(await asyncio.wait_for(reader.readline(), timeout=30) or b"{}")
        except (TimeoutError, ValueError) as exc:
            raise SessionError(504, "driver_timeout", "the agent did not answer the config change") from exc
        finally:
            writer.close()
        if not reply.get("ok"):
            raise SessionError(409, "config_rejected", reply.get("error") or "the agent refused the change")
        # A new model resets the thinking level to that model's default.
        prefs = {MODEL_CATEGORY: value} if category == MODEL_CATEGORY else {**self._preferences(), category: value}
        write_json_atomic(self.runtime_dir / "preferences.json", prefs)
        return {"options": reply["options"], "ready": True}

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
