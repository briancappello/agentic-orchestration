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

    store: Path
    sortie_url: str
    sortie_token: str
    password_hash: str
    secret_key: str
    broker_command: list[str] = field(default_factory=lambda: ["acp-broker"])
    agent_command: list[str] = field(default_factory=lambda: ["opencode", "acp"])
    # Selected through the agent's ACP "model" config option; empty keeps the agent's default.
    agent_model: str = ""
    prompt_file: Path | None = None
    frontend_dir: Path | None = None
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

        store = Path(need("WORKBENCH_STORE")).expanduser().resolve()
        if not (store / "openspec").is_dir():
            raise ConfigError(f"WORKBENCH_STORE {store} has no openspec/ directory")
        here = Path(__file__).resolve().parents[2]
        prompt = env.get("WORKBENCH_PROMPT_FILE") or str(here / "prompts" / "planning-session.md")
        frontend = env.get("WORKBENCH_FRONTEND_DIR") or str(here / "frontend" / "dist")
        return cls(
            store=store,
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
