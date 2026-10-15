"""Workbench configuration, read from the environment."""

from __future__ import annotations

import os
import shlex
from dataclasses import dataclass, field
from pathlib import Path


DEFAULT_AGENT_MODEL = "anthropic/claude-opus-5-5"


class ConfigError(Exception):
    """The configuration is incomplete or invalid."""


@dataclass(frozen=True)
class Config:
    """Everything the backend needs. Tokens stay server-side: no response carries them."""

    # Where the registry database and the stores of created projects live.
    home: Path
    sortie_url: str
    sortie_token: str
    password_hash: str
    secret_key: str
    broker_command: list[str] = field(default_factory=lambda: ["acp-broker"])
    agent_command: list[str] = field(default_factory=lambda: ["opencode", "acp"])
    # Selected through the agent's ACP "model" config option; empty keeps the agent's default.
    agent_model: str = ""
    # A store to register as a project at startup, once, with its tracker project.
    store: Path | None = None
    huly_project: str = ""
    prompt_file: Path | None = None
    frontend_dir: Path | None = None
    # The parent of each project's session runtime directory.
    runtime_dir: Path | None = None
    session_max_age: int = 12 * 3600
    debounce_ms: int = 300
    poll_seconds: float = 5.0
    cookie_secure: bool = False

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "Config":
        env = dict(os.environ if env is None else env)

        def need(key: str) -> str:
            value = env.get(key, "").strip()
            if not value:
                raise ConfigError(f"{key} is required")
            return value

        default_home = Path(env.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "plan-workbench"
        home = Path(env.get("WORKBENCH_HOME") or default_home).expanduser().resolve()
        store = None
        huly_project = env.get("WORKBENCH_HULY_PROJECT", "").strip()
        if env.get("WORKBENCH_STORE", "").strip():
            store = Path(env["WORKBENCH_STORE"].strip()).expanduser().resolve()
            if not (store / "openspec").is_dir():
                raise ConfigError(f"WORKBENCH_STORE {store} has no openspec/ directory")
            if not huly_project:
                raise ConfigError("WORKBENCH_HULY_PROJECT is required with WORKBENCH_STORE: the Huly project the store syncs into")
        here = Path(__file__).resolve().parents[2]
        prompt = env.get("WORKBENCH_PROMPT_FILE") or str(here / "prompts" / "planning-session.md")
        frontend = env.get("WORKBENCH_FRONTEND_DIR") or str(here / "frontend" / "dist")
        return cls(
            home=home,
            store=store,
            huly_project=huly_project,
            sortie_url=need("WORKBENCH_SORTIE_URL").rstrip("/"),
            sortie_token=env.get("WORKBENCH_SORTIE_TOKEN", ""),
            password_hash=need("WORKBENCH_PASSWORD_HASH"),
            secret_key=need("WORKBENCH_SECRET_KEY"),
            broker_command=shlex.split(env.get("WORKBENCH_BROKER_COMMAND", "acp-broker")),
            agent_command=shlex.split(env.get("WORKBENCH_AGENT_COMMAND", "opencode acp")),
            agent_model=env.get("WORKBENCH_AGENT_MODEL", DEFAULT_AGENT_MODEL).strip(),
            prompt_file=Path(prompt),
            frontend_dir=Path(frontend),
            runtime_dir=Path(env["WORKBENCH_RUNTIME_DIR"]).expanduser() if env.get("WORKBENCH_RUNTIME_DIR") else None,
            cookie_secure=env.get("WORKBENCH_COOKIE_SECURE", "") == "1",
        )
