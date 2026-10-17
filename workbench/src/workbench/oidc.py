"""OpenID Connect sign-in: discovery, the authorization code flow with PKCE,
and ID token validation, on httpx and joserfc."""

from __future__ import annotations

import base64
import hashlib
import secrets
import time
from typing import Any
from urllib.parse import urlencode

import httpx
from joserfc import jwt
from joserfc.errors import JoseError
from joserfc.jwk import KeySet

LEEWAY = 60


class OIDCError(Exception):
    """A sign-in could not be verified. The message is safe to show."""


def pkce_pair() -> tuple[str, str]:
    """A PKCE verifier and its S256 challenge."""
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    return verifier, challenge


class OIDCClient:
    def __init__(self, issuer: str, client_id: str, client_secret: str, redirect_url: str,
                 transport: httpx.AsyncBaseTransport | None = None, now=time.time, scopes: str = "openid profile email"):
        self.issuer = issuer.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_url = redirect_url
        self.scopes = scopes if "openid" in scopes.split() else "openid " + scopes
        self._http = httpx.AsyncClient(transport=transport, timeout=15)
        self._now = now
        self._discovery: dict[str, Any] | None = None
        self._keys: KeySet | None = None

    async def aclose(self) -> None:
        await self._http.aclose()

    async def discovery(self) -> dict[str, Any]:
        if self._discovery is None:
            r = await self._http.get(self.issuer + "/.well-known/openid-configuration")
            r.raise_for_status()
            doc = r.json()
            if doc.get("issuer", "").rstrip("/") != self.issuer:
                raise OIDCError("the provider's discovery document names another issuer")
            self._discovery = doc
        return self._discovery

    async def _keyset(self, refresh: bool = False) -> KeySet:
        if self._keys is None or refresh:
            r = await self._http.get((await self.discovery())["jwks_uri"])
            r.raise_for_status()
            self._keys = KeySet.import_key_set(r.json())
        return self._keys

    async def authorize_url(self, state: str, nonce: str, challenge: str) -> str:
        endpoint = (await self.discovery())["authorization_endpoint"]
        query = urlencode({
            "response_type": "code", "client_id": self.client_id, "redirect_uri": self.redirect_url,
            "scope": self.scopes, "state": state, "nonce": nonce,
            "code_challenge": challenge, "code_challenge_method": "S256",
        })
        return f"{endpoint}?{query}"

    async def end_session_url(self) -> str | None:
        return (await self.discovery()).get("end_session_endpoint")

    async def exchange(self, code: str, verifier: str, nonce: str) -> dict[str, Any]:
        """Trade the code for tokens and return the validated ID token's claims.
        Only the ID token is used; no token leaves the backend."""
        r = await self._http.post((await self.discovery())["token_endpoint"], data={
            "grant_type": "authorization_code", "code": code, "redirect_uri": self.redirect_url,
            "client_id": self.client_id, "client_secret": self.client_secret, "code_verifier": verifier,
        }, headers={"Accept": "application/json"})
        if r.status_code != 200:
            raise OIDCError(f"the provider refused the sign-in code ({r.status_code})")
        id_token = r.json().get("id_token")
        if not id_token:
            raise OIDCError("the provider returned no ID token")
        return await self.validate(id_token, nonce)

    async def validate(self, id_token: str, nonce: str) -> dict[str, Any]:
        try:
            token = await self._decode(id_token)
        except JoseError as exc:
            raise OIDCError(f"the ID token's signature could not be verified: {exc.description or exc.error}") from exc
        c = token.claims
        now = self._now()
        if str(c.get("iss", "")).rstrip("/") != self.issuer:
            raise OIDCError("the ID token is from another issuer")
        aud = c.get("aud")
        if aud != self.client_id and not (isinstance(aud, list) and self.client_id in aud):
            raise OIDCError("the ID token is for another client")
        if not isinstance(c.get("exp"), (int, float)) or c["exp"] < now - LEEWAY:
            raise OIDCError("the ID token has expired")
        if isinstance(c.get("nbf"), (int, float)) and c["nbf"] > now + LEEWAY:
            raise OIDCError("the ID token is not valid yet")
        if isinstance(c.get("iat"), (int, float)) and c["iat"] > now + LEEWAY:
            raise OIDCError("the ID token was issued in the future")
        if not nonce or c.get("nonce") != nonce:
            raise OIDCError("the ID token does not answer this sign-in")
        if not c.get("sub"):
            raise OIDCError("the ID token names no subject")
        return dict(c)

    async def _decode(self, id_token: str):
        keys = await self._keyset()
        try:
            return jwt.decode(id_token, keys)
        except JoseError:
            # The provider may have rotated its keys: read them once more.
            return jwt.decode(id_token, await self._keyset(refresh=True))
