"""The workers Sortie runs for a project's stories: what the graph shows of them."""

from __future__ import annotations

from typing import Any


def worker_fields(state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """The fields each worker adds to its story's runtime, by tracker identifier."""
    out: dict[str, dict[str, Any]] = {}
    for r in state.get("running") or []:
        out[r["issue_identifier"]] = {
            "stage": r.get("rule_name") or None,
            "session_id": r.get("session_id") or None,
            "held": bool(r.get("held")),
            "holder": r.get("holder") or None,
            "watchable": bool((r.get("broker") or {}).get("http_url")),
        }
    for r in state.get("retrying") or []:
        out.setdefault(r["issue_identifier"], {"stage": None, "session_id": None, "held": False, "holder": None, "watchable": False})
    return out
