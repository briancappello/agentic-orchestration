"""An in-memory Sortie plan API behind httpx.MockTransport."""

from __future__ import annotations

import json
from typing import Any

import httpx

from tests.workbench.conftest import SORTIE_TOKEN
from workbench.sortie import SortieClient


class FakeSortie:
    def __init__(self):
        self.nodes: list[dict[str, Any]] = []
        self.edges: list[dict[str, str]] = []
        self.capabilities = ["create_issue", "update_issue", "set_parent", "link_dependency"]
        self.down = False
        self.requests: list[tuple[str, str, Any]] = []
        self.previews: dict[str, dict[str, Any]] = {}
        self.applied: list[dict[str, Any]] = []

    def issue(self, plan_key, kind="story", state="Todo", parent=None, runtime=None, terminal=False):
        node = {
            "id": f"id-{len(self.nodes) + 1}", "identifier": f"T-{len(self.nodes) + 1}", "plan_key": plan_key,
            "kind": kind, "title": f"tracker {plan_key}", "state": state, "terminal": terminal,
            "url": f"https://tracker/{len(self.nodes) + 1}", "parent_id": parent, "runtime": runtime,
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
        if path == "/api/v1/plan/graph":
            return httpx.Response(200, json={"generated_at": "now", "capabilities": self.capabilities, "nodes": self.nodes, "edges": self.edges})
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
            self.applied.append(body)
            return httpx.Response(200, json={"result": {"created": [], "failed": None}})
        return httpx.Response(404, json={"error": {"code": "not_found", "message": path}})
