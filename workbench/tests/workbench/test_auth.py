from __future__ import annotations

from fastapi.testclient import TestClient

from workbench.app import create_app
from workbench.auth import COOKIE_NAME, Sessions, hash_password, local_identity, verify_password
from tests.workbench.conftest import BROKER_TOKEN, PASSWORD, SORTIE_TOKEN, make_config, sign_in


def test_password_hash_round_trip():
    h = hash_password("pw")
    assert h.startswith("scrypt$") and verify_password("pw", h)
    assert not verify_password("other", h)
    assert not verify_password("pw", "garbage")


def test_unauthenticated_requests_get_401(config):
    client = TestClient(create_app(config))
    r = client.get("/api/me")
    assert r.status_code == 401
    assert r.json() == {"error": {"code": "unauthorized", "message": "sign in first"}}


def test_sign_in_sets_signed_httponly_cookie(config):
    client = TestClient(create_app(config))
    r = client.post("/api/login", json={"password": PASSWORD})
    assert r.status_code == 200
    cookie = r.headers["set-cookie"]
    assert COOKIE_NAME in cookie and "HttpOnly" in cookie and "samesite=strict" in cookie.lower()
    assert client.get("/api/me").status_code == 200

    client.post("/api/logout")
    assert client.get("/api/me").status_code == 401


def test_wrong_password_and_forged_cookie_are_refused(config):
    client = TestClient(create_app(config))
    assert client.post("/api/login", json={"password": "nope"}).status_code == 401
    client.cookies.set(COOKIE_NAME, Sessions("other-secret", 60).issue(local_identity()))
    assert client.get("/api/me").status_code == 401


def test_no_response_carries_the_tokens(store):
    store.plan([])
    cfg = make_config(store.root, broker_command=["acp-broker", "--token", BROKER_TOKEN])
    client = TestClient(create_app(cfg))
    responses = [client.get("/api/me"), client.post("/api/login", json={"password": PASSWORD})]
    sign_in(client)
    responses += [client.get("/api/me"), client.post("/api/logout")]
    for r in responses:
        blob = r.text + "".join(f"{k}:{v}" for k, v in r.headers.items())
        assert SORTIE_TOKEN not in blob and BROKER_TOKEN not in blob
