"""An in-memory Sortie plan API behind httpx.MockTransport."""

from __future__ import annotations

import json
from typing import Any

import httpx

from tests.workbench.conftest import SORTIE_TOKEN
from workbench.sortie import SortieClient


class FakeSortie:
    """Serves tracker workspace projects; ``nodes`` and ``edges`` are the
    configured project's (``T``), the one Sortie dispatches."""

    DEFAULT = "T"

    def __init__(self):
        # Tracker projects of the workspace: key -> {"name", "problems"}.
        self.projects: dict[str, dict[str, Any]] = {self.DEFAULT: {"name": "Tracker", "problems": []}}
        self.ensure_error: tuple[int, str] | None = None
        self.nodes: list[dict[str, Any]] = []
        self.edges: list[dict[str, str]] = []
        self.capabilities = ["create_issue", "update_issue", "set_parent", "link_dependency"]
        self.down = False
        self.requests: list[tuple[str, str, Any]] = []
        self.previews: dict[str, dict[str, Any]] = {}
        self.applied: list[dict[str, Any]] = []
        # Plan control: the state names, and the plan keys pulled back or cancelled.
        self.plan_states: dict[str, str] | None = None
        self.pulled_back: list[str] = []
        self.cancelled: list[str] = []
        self.claimed: set[str] = set()

    def issue(self, plan_key, kind="story", state="Todo", parent=None, runtime=None, terminal=False, **extra):
        node = {
            "id": f"id-{len(self.nodes) + 1}", "identifier": f"T-{len(self.nodes) + 1}", "plan_key": plan_key,
            "kind": kind, "title": f"tracker {plan_key}", "state": state, "terminal": terminal,
            "url": f"https://tracker/{len(self.nodes) + 1}", "parent_id": parent, "runtime": runtime, **extra,
        }
        self.nodes.append(node)
        return node

    def client(self) -> SortieClient:
        return SortieClient("http://sortie.test", SORTIE_TOKEN, transport=httpx.MockTransport(self.handle))

    def handle(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else None
        self.requests.append((request.method, request.url.path, body))
        if request.headers.get("authorization") != f"Bearer {SORTIE_TOKEN}":
            return httpx.Response(401, json={"error": {"code": "unauthorized", "message": "token"}})
        if self.down:
            return httpx.Response(502, json={"error": {"code": "tracker_transport_error", "message": "tracker down"}})
        path = request.url.path
        project = request.url.params.get("project") or self.DEFAULT
        if path.startswith("/api/v1/plan/projects/"):
            return self.handle_project(request.method, path.rsplit("/", 1)[1], body)
        if path.startswith("/api/v1/plan/") and project not in self.projects:
            return httpx.Response(404, json={"error": {"code": "project_not_found", "message": f"plan: project not found: {project}"}})
        if path == "/api/v1/plan/graph":
            own = project == self.DEFAULT
            return httpx.Response(200, json={
                "project": project, "dispatched": own, "generated_at": "now", "capabilities": self.capabilities,
                "nodes": self.nodes if own else [], "edges": self.edges if own else [],
                "plan_states": self.plan_states,
            })
        if path in ("/api/v1/plan/pull-back", "/api/v1/plan/cancel"):
            key = body["plan_key"]
            node = next((n for n in self.nodes if n["plan_key"] == key), None)
            if node is None:
                return httpx.Response(404, json={"error": {"code": "issue_not_found", "message": key}})
            if path.endswith("pull-back"):
                if key in self.claimed:
                    return httpx.Response(409, json={"error": {"code": "already_claimed", "message": key}})
                self.pulled_back.append(key)
                node["state"] = (self.plan_states or {}).get("backlog", "Backlog")
            else:
                self.cancelled.append(key)
                node["state"], node["terminal"] = (self.plan_states or {}).get("cancel", "Canceled"), True
            return httpx.Response(200, json={"plan_key": key})
        if path == "/api/v1/plan/capabilities":
            return httpx.Response(200, json={"capabilities": self.capabilities, "plan_key_storage": "custom_field"})
        if path == "/api/v1/plan/sync":
            graph = body["graph"]
            if not body.get("apply"):
                pid = f"p{len(self.previews) + 1}"
                approved = [n for n in graph["nodes"] if n["approval"] == "approved"]
                missing = [] if "link_dependency" in self.capabilities else ["link_dependency"]
                preview = {"counts": {"creates": len(approved), "updates": 0, "parents": 0,
                                      "relations_added": len(graph["blocks"]), "relations_removed": 0, "orphans": 0},
                           "missing_capabilities": missing, "skipped_drafts": [], "source_digest": graph["source_digest"]}
                self.previews[pid] = preview
                return httpx.Response(200, json={"preview_id": pid, "preview": preview, "capabilities": self.capabilities})
            if body["preview_id"] not in self.previews:
                return httpx.Response(409, json={"error": {"code": "stale_preview", "message": "unknown preview"}})
            self.applied.append({**body, "project": project})
            return httpx.Response(200, json={"result": {"created": [], "failed": None}})
        return httpx.Response(404, json={"error": {"code": "not_found", "message": path}})

    def handle_project(self, method: str, key: str, body: Any) -> httpx.Response:
        def view(created: bool) -> dict[str, Any]:
            p = self.projects.get(key)
            return {"key": key, "name": p["name"] if p else None, "url": f"https://tracker/{key}" if p else None,
                    "exists": p is not None, "created": created, "ready": bool(p) and not p["problems"],
                    "dispatched": key == self.DEFAULT, "problems": list(p["problems"]) if p else []}

        if method == "GET":
            return httpx.Response(200, json=view(False))
        if self.ensure_error:
            status, code = self.ensure_error
            return httpx.Response(status, json={"error": {"code": code, "message": "ensure failed"}})
        created = key not in self.projects
        if created:
            self.projects[key] = {"name": (body or {}).get("name") or key, "problems": []}
        return httpx.Response(200, json=view(created))
