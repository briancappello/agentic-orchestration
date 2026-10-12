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

    async def plan_graph(self, include_unkeyed: bool = False) -> dict[str, Any]:
        params = {"include_unkeyed": "true"} if include_unkeyed else None
        return await self._request("GET", "/api/v1/plan/graph", params=params)

    async def capabilities(self) -> dict[str, Any]:
        return await self._request("GET", "/api/v1/plan/capabilities")

    async def preview(self, graph: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", "/api/v1/plan/sync", json={"graph": graph, "apply": False})

    async def apply(self, graph: dict[str, Any], preview_id: str) -> dict[str, Any]:
        return await self._request(
            "POST", "/api/v1/plan/sync", json={"graph": graph, "apply": True, "preview_id": preview_id}, timeout=600
        )
