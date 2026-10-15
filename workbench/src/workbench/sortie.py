"""Sortie's plan API, called with the workbench's server-side token."""

from __future__ import annotations

from typing import Any

import httpx


class SortieError(Exception):
    """Sortie answered with an error, or could not be reached."""

    def __init__(self, status: int, code: str, message: str, body: dict[str, Any] | None = None):
        super().__init__(f"{code}: {message}")
        self.status = status
        self.code = code
        self.message = message
        self.body = body or {}


class SortieClient:
    def __init__(self, base_url: str, token: str, transport: httpx.AsyncBaseTransport | None = None, timeout: float = 30.0):
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        self._client = httpx.AsyncClient(base_url=base_url, headers=headers, transport=transport, timeout=timeout)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _request(self, method: str, path: str, *, timeout: float | None = None, **kwargs) -> dict[str, Any]:
        try:
            r = await self._client.request(method, path, timeout=timeout or httpx.USE_CLIENT_DEFAULT, **kwargs)
        except httpx.HTTPError as exc:
            raise SortieError(0, "sortie_unreachable", f"cannot reach Sortie: {exc}") from exc
        try:
            body = r.json()
        except ValueError:
            body = {}
        if r.status_code >= 400:
            err = body.get("error") if isinstance(body, dict) else None
            code = err.get("code", "sortie_error") if isinstance(err, dict) else "sortie_error"
            message = err.get("message", r.text) if isinstance(err, dict) else r.text
            raise SortieError(r.status_code, code, message, body if isinstance(body, dict) else None)
        return body

    async def plan_graph(self, include_unkeyed: bool = False, project: str | None = None) -> dict[str, Any]:
        params = {"include_unkeyed": "true"} if include_unkeyed else {}
        if project:
            params["project"] = project
        return await self._request("GET", "/api/v1/plan/graph", params=params or None)

    async def capabilities(self, project: str | None = None) -> dict[str, Any]:
        return await self._request("GET", "/api/v1/plan/capabilities", params={"project": project} if project else None)

    async def preview(self, graph: dict[str, Any], project: str | None = None) -> dict[str, Any]:
        return await self._request("POST", "/api/v1/plan/sync", params={"project": project} if project else None,
                                   json={"graph": graph, "apply": False})

    async def apply(self, graph: dict[str, Any], preview_id: str, project: str | None = None) -> dict[str, Any]:
        return await self._request(
            "POST", "/api/v1/plan/sync", params={"project": project} if project else None,
            json={"graph": graph, "apply": True, "preview_id": preview_id}, timeout=600,
        )

    async def project(self, key: str) -> dict[str, Any]:
        """Whether the tracker project exists and what keeps plan writes from working in it."""
        return await self._request("GET", f"/api/v1/plan/projects/{key}")

    async def ensure_project(self, key: str, name: str) -> dict[str, Any]:
        """Create the tracker project when it is missing, then report it."""
        return await self._request("PUT", f"/api/v1/plan/projects/{key}", json={"name": name})

    def bind(self, project: str) -> "ProjectSortie":
        return ProjectSortie(self, project)


class ProjectSortie:
    """The plan API of one tracker project, through a shared client."""

    def __init__(self, client: SortieClient, project: str):
        self.client = client
        self.project = project

    async def plan_graph(self, include_unkeyed: bool = False) -> dict[str, Any]:
        return await self.client.plan_graph(include_unkeyed, project=self.project)

    async def capabilities(self) -> dict[str, Any]:
        return await self.client.capabilities(project=self.project)

    async def preview(self, graph: dict[str, Any]) -> dict[str, Any]:
        return await self.client.preview(graph, project=self.project)

    async def apply(self, graph: dict[str, Any], preview_id: str) -> dict[str, Any]:
        return await self.client.apply(graph, preview_id, project=self.project)
