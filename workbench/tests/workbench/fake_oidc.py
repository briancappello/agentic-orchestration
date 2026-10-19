"""An OpenID Connect provider for tests, served through httpx's mock transport."""

from __future__ import annotations

import time
from urllib.parse import parse_qs, urlparse

import httpx
from joserfc import jwt
from joserfc.jwk import KeySet, RSAKey

ISSUER = "https://id.example"
CLIENT_ID = "workbench"
CLIENT_SECRET = "client-secret-0123456789"
REDIRECT = "http://testserver/api/auth/callback"


class FakeProvider:
    def __init__(self):
        self.keys = [RSAKey.generate_key(2048, parameters={"kid": "k1", "alg": "RS256", "use": "sig"})]
        self.claims: dict = {"sub": "ana", "name": "Ana Ruiz", "email": "ana@example.com", "groups": ["eng", "plan-approvers"]}
        self.codes: dict[str, dict] = {}
        self.token_overrides: dict = {}
        self.jwks_reads = 0
        self.issued_tokens: list[str] = []
        self.sign_with = None  # a key outside the JWKS, to forge

    def rotate(self) -> None:
        self.keys.append(RSAKey.generate_key(2048, parameters={"kid": f"k{len(self.keys) + 1}", "alg": "RS256", "use": "sig"}))

    def authorize(self, url: str) -> tuple[str, str]:
        """Play the person signing in at the provider: return the code and state
        the provider would redirect back with."""
        q = {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}
        assert q["code_challenge_method"] == "S256" and q["client_id"] == CLIENT_ID and q["redirect_uri"] == REDIRECT
        code = f"code-{len(self.codes)}"
        self.codes[code] = {"nonce": q["nonce"], "challenge": q["code_challenge"]}
        return code, q["state"]

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/.well-known/openid-configuration":
            return httpx.Response(200, json={
                "issuer": ISSUER, "authorization_endpoint": ISSUER + "/authorize", "token_endpoint": ISSUER + "/token",
                "jwks_uri": ISSUER + "/jwks", "end_session_endpoint": ISSUER + "/logout",
            })
        if path == "/jwks":
            self.jwks_reads += 1
            return httpx.Response(200, json=KeySet(self.keys).as_dict(private=False))
        if path == "/token":
            form = {k: v[0] for k, v in parse_qs(request.content.decode()).items()}
            grant = self.codes.pop(form.get("code", ""), None)
            if grant is None or form.get("client_secret") != CLIENT_SECRET:
                return httpx.Response(400, json={"error": "invalid_grant"})
            now = int(time.time())
            claims = {"iss": ISSUER, "aud": CLIENT_ID, "iat": now, "exp": now + 300, "nonce": grant["nonce"], **self.claims, **self.token_overrides}
            key = self.sign_with or self.keys[-1]
            token = jwt.encode({"alg": "RS256", "kid": key.kid}, claims, key)
            self.issued_tokens.append(token)
            return httpx.Response(200, json={"id_token": token, "access_token": "provider-access-token", "token_type": "Bearer"})
        return httpx.Response(404)

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handler)
