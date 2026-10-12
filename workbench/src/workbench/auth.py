"""One operator password and a signed, HttpOnly session cookie."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

COOKIE_NAME = "workbench_session"

_N, _R, _P = 2**14, 8, 1


def hash_password(password: str, *, salt: bytes | None = None) -> str:
    """Return "scrypt$n$r$p$salt$hash" for password."""
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=32)
    b64 = lambda b: base64.urlsafe_b64encode(b).decode().rstrip("=")  # noqa: E731
    return f"scrypt${_N}${_R}${_P}${b64(salt)}${b64(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt, digest = stored.split("$")
        if scheme != "scrypt":
            return False
        unb64 = lambda s: base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))  # noqa: E731
        got = hashlib.scrypt(password.encode(), salt=unb64(salt), n=int(n), r=int(r), p=int(p), dklen=32)
        return hmac.compare_digest(got, unb64(digest))
    except (ValueError, TypeError):
        return False


class Sessions:
    """Issues and checks signed session cookies."""

    def __init__(self, secret_key: str, max_age: int):
        self._serializer = URLSafeTimedSerializer(secret_key, salt="workbench-session")
        self.max_age = max_age

    def issue(self) -> str:
        return self._serializer.dumps({"operator": True, "nonce": secrets.token_hex(8)})

    def valid(self, cookie: str | None) -> bool:
        if not cookie:
            return False
        try:
            data = self._serializer.loads(cookie, max_age=self.max_age)
        except (BadSignature, SignatureExpired):
            return False
        return isinstance(data, dict) and data.get("operator") is True
