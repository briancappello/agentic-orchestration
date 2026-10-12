"""The ACP client of one planning session, run as its own detached process.

The broker ends its session when its driver closes the broker's standard
input. So the driver must outlive the workbench backend: a reload, a crash,
or Ctrl-C on the backend must not end the conversation. The backend starts
this module with ``start_new_session=True`` and talks to the session only
through the broker's HTTP viewer transport.

The driver starts the broker, opens one ACP session in the spec store,
sends the planning prompt as the first turn, and then answers what reaches
the driver: a permission request no viewer answered is cancelled, never
granted on a person's behalf. It records its state in ``state.json`` in the
runtime directory and exits when the broker exits or on SIGTERM.

Run: ``python -m workbench.session_driver <runtime-dir>``; the directory
holds ``spec.json``, written by the backend.
"""

from __future__ import annotations

import asyncio
import json
import os
import secrets
import signal
import socket
import sys
import time
from pathlib import Path
from typing import Any

ACP_PROTOCOL_VERSION = 1
REGISTRY_TIMEOUT = 15.0


def write_json(path: Path, data: dict[str, Any]) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data))
    os.replace(tmp, path)


class Driver:
    def __init__(self, runtime: Path):
        self.runtime = runtime
        self.spec = json.loads((runtime / "spec.json").read_text())
        self.key: str = self.spec["key"]
        self.state: dict[str, Any] = {
            "key": self.key, "store": self.spec["store"], "driver_pid": os.getpid(), "broker_pid": None,
            "http_url": None, "token_file": None, "acp_session_id": None,
            "started_at": time.time(), "ended_at": None, "error": None,
        }
        self.proc: asyncio.subprocess.Process | None = None
        self.next_id = 0
        self.waiting: dict[int, asyncio.Future] = {}

    def save(self, **changes: Any) -> None:
        self.state.update(changes)
        write_json(self.runtime / "state.json", self.state)

    async def run(self) -> int:
        loop = asyncio.get_running_loop()
        stop = asyncio.Event()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, stop.set)
        try:
            await self.start_broker()
            reader = asyncio.create_task(self.read())
            setup = asyncio.create_task(self.open_session())
            stopper = asyncio.create_task(stop.wait())
            await asyncio.wait({reader, stopper}, return_when=asyncio.FIRST_COMPLETED)
            setup.cancel()
        except Exception as exc:  # recorded for the backend to show
            self.save(error=str(exc))
        finally:
            await self.stop_broker()
            self.save(ended_at=time.time())
        return 0

    async def start_broker(self) -> None:
        token = secrets.token_urlsafe(32)
        token_file = self.runtime / f"{self.key}.token"
        token_file.write_text(token)
        os.chmod(token_file, 0o600)
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        registry = self.runtime / "registry"
        argv = [
            *self.spec["broker_command"],
            "-key", self.key,
            "-registry-dir", str(registry),
            "-http", f"127.0.0.1:{port}",
            "-viewer-token-file", str(token_file),
            "-handback-grace", "24h",
            "--", *self.spec["agent_command"],
        ]
        self.proc = await asyncio.create_subprocess_exec(
            *argv, cwd=self.spec["store"],
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=open(self.runtime / f"{self.key}.stderr", "wb"),  # noqa: SIM115
        )
        self.save(broker_pid=self.proc.pid, token_file=str(token_file))

        deadline = time.monotonic() + REGISTRY_TIMEOUT
        while time.monotonic() < deadline:
            if self.proc.returncode is not None:
                raise RuntimeError(f"acp-broker exited with code {self.proc.returncode}")
            for rec_path in registry.glob(f"{self.key}.*.json"):
                try:
                    rec = json.loads(rec_path.read_text())
                except (OSError, ValueError):
                    continue
                if rec.get("pid") == self.proc.pid and rec.get("http_url"):
                    self.save(http_url=rec["http_url"].rstrip("/"))
                    return
            await asyncio.sleep(0.05)
        raise RuntimeError("acp-broker did not register in time")

    async def stop_broker(self) -> None:
        proc = self.proc
        if proc is None or proc.returncode is not None:
            return
        if proc.stdin and not proc.stdin.is_closing():
            proc.stdin.close()
        proc.terminate()
        try:
            await asyncio.wait_for(proc.wait(), timeout=10)
        except TimeoutError:
            proc.kill()
            await proc.wait()

    async def open_session(self) -> None:
        try:
            await self._open_session()
        except Exception as exc:  # recorded for the backend to show; the session stays up
            self.save(error=str(exc))

    async def _open_session(self) -> None:
        await self.call("initialize", {
            "protocolVersion": ACP_PROTOCOL_VERSION,
            "clientCapabilities": {"fs": {"readTextFile": False, "writeTextFile": False}, "terminal": False},
            "clientInfo": {"name": "plan-workbench", "version": "0.1.0"},
        })
        new = await self.call("session/new", {"cwd": self.spec["store"], "mcpServers": []})
        self.save(acp_session_id=new.get("sessionId"))
        prompt = self.spec.get("prompt") or ""
        if prompt:
            await self.call("session/prompt", {"sessionId": new.get("sessionId"), "prompt": [{"type": "text", "text": prompt}]})

    async def call(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        self.next_id += 1
        msg_id = self.next_id
        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        self.waiting[msg_id] = fut
        await self.send({"jsonrpc": "2.0", "id": msg_id, "method": method, "params": params})
        reply = await fut
        if "error" in reply:
            raise RuntimeError(f"{method}: {reply['error'].get('message')}")
        return reply.get("result") or {}

    async def send(self, msg: dict[str, Any]) -> None:
        assert self.proc and self.proc.stdin
        self.proc.stdin.write((json.dumps(msg) + "\n").encode())
        await self.proc.stdin.drain()

    async def read(self) -> None:
        assert self.proc and self.proc.stdout
        while line := await self.proc.stdout.readline():
            try:
                msg = json.loads(line)
            except ValueError:
                continue
            if "method" not in msg and msg.get("id") in self.waiting:
                self.waiting.pop(msg["id"]).set_result(msg)
            elif "method" in msg and "id" in msg:
                if msg["method"] == "session/request_permission":
                    await self.send({"jsonrpc": "2.0", "id": msg["id"], "result": {"outcome": {"outcome": "cancelled"}}})
                else:
                    await self.send({"jsonrpc": "2.0", "id": msg["id"],
                                     "error": {"code": -32601, "message": f"{msg['method']} is not supported by the workbench"}})


def main() -> int:
    runtime = Path(sys.argv[1])
    return asyncio.run(Driver(runtime).run())


if __name__ == "__main__":
    sys.exit(main())
