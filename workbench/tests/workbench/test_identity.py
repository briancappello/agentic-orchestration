from __future__ import annotations

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from joserfc.jwk import RSAKey

from tests.workbench.conftest import PASSWORD, make_config, sign_in
from tests.workbench.fake_oidc import CLIENT_ID, CLIENT_SECRET, ISSUER, REDIRECT, FakeProvider
from workbench.app import create_app
from workbench.auth import APPROVER, COOKIE_NAME, PLANNER, Sessions, roles_from_groups, safe_next
from workbench.config import Config, ConfigError
from workbench.oidc import OIDCClient


# Configuration


BASE_ENV = {"WORKBENCH_SORTIE_URL": "http://sortie.test", "WORKBENCH_SECRET_KEY": "k"}
OIDC_ENV = {
    **BASE_ENV, "WORKBENCH_OIDC_ISSUER": ISSUER + "/", "WORKBENCH_OIDC_CLIENT_ID": CLIENT_ID,
    "WORKBENCH_OIDC_CLIENT_SECRET": CLIENT_SECRET, "WORKBENCH_OIDC_REDIRECT_URL": REDIRECT,
    "WORKBENCH_OIDC_PLANNER_GROUP": "eng", "WORKBENCH_OIDC_APPROVER_GROUP": "plan-approvers",
}


def test_config_oidc_mode():
    cfg = Config.from_env(OIDC_ENV)
    assert cfg.oidc and cfg.oidc_issuer == ISSUER and cfg.oidc_roles_claim == "groups" and cfg.password_hash == ""


@pytest.mark.parametrize("missing", [
    "WORKBENCH_OIDC_CLIENT_ID", "WORKBENCH_OIDC_REDIRECT_URL", "WORKBENCH_OIDC_PLANNER_GROUP",
    "WORKBENCH_OIDC_APPROVER_GROUP", "WORKBENCH_OIDC_CLIENT_SECRET",
])
def test_config_partial_oidc_is_refused(missing):
    env = {k: v for k, v in OIDC_ENV.items() if k != missing}
    with pytest.raises(ConfigError, match="WORKBENCH_OIDC_CLIENT_SECRET" if "SECRET" in missing else missing):
        Config.from_env(env)


def test_config_secret_file(tmp_path):
    secret = tmp_path / "secret"
    secret.write_text(CLIENT_SECRET + "\n")
    env = {k: v for k, v in OIDC_ENV.items() if k != "WORKBENCH_OIDC_CLIENT_SECRET"}
    env["WORKBENCH_OIDC_CLIENT_SECRET_FILE"] = str(secret)
    assert Config.from_env(env).oidc_client_secret == CLIENT_SECRET


def test_config_local_mode_needs_a_password_hash():
    with pytest.raises(ConfigError, match="WORKBENCH_PASSWORD_HASH"):
        Config.from_env(BASE_ENV)
    assert not Config.from_env({**BASE_ENV, "WORKBENCH_PASSWORD_HASH": "scrypt$x"}).oidc


# Roles and sessions


@pytest.mark.parametrize(("groups", "roles"), [
    (["eng"], (PLANNER,)),
    (["eng", "plan-approvers"], (PLANNER, APPROVER)),
    (["plan-approvers"], (PLANNER, APPROVER)),
    (["sales"], ()),
    ("plan-approvers", (PLANNER, APPROVER)),
    (None, ()),
])
def test_roles_from_groups(groups, roles):
    assert roles_from_groups(groups, "eng", "plan-approvers") == roles


def test_a_cookie_from_before_identities_no_longer_counts():
    from itsdangerous import URLSafeTimedSerializer

    old = URLSafeTimedSerializer("s", salt="workbench-session").dumps({"operator": True, "nonce": "x"})
    assert Sessions("s", 60).identity(old) is None


@pytest.mark.parametrize(("path", "want"), [
    ("/#/projects/a", "/#/projects/a"), ("https://evil.example/", "/"), ("//evil.example/", "/"), ("", "/"), ("/\\evil", "/"),
])
def test_safe_next(path, want):
    assert safe_next(path) == want


# Every route declares a check


PUBLIC = {"/api/auth/mode", "/api/login", "/api/auth/login", "/api/auth/callback", "/api/logout"}


def _depends_on_identity(route: APIRoute) -> bool:
    stack = list(route.dependant.dependencies)
    while stack:
        d = stack.pop()
        if getattr(d.call, "__name__", "") in ("current_identity", "check"):
            return True
        stack.extend(d.dependencies)
    return False


def test_every_api_route_declares_a_check(config):
    app = create_app(config)
    open_routes = [r.path for r in app.routes if isinstance(r, APIRoute) and r.path.startswith("/api")
                   and r.path not in PUBLIC and not _depends_on_identity(r)]
    assert open_routes == []


# The OIDC flow


@pytest.fixture
def provider():
    return FakeProvider()


@pytest.fixture
def oidc_app(store, provider):
    store.plan([])
    cfg = make_config(store.root, password_hash="", oidc_issuer=ISSUER, oidc_client_id=CLIENT_ID, oidc_client_secret=CLIENT_SECRET,
                      oidc_redirect_url=REDIRECT, oidc_planner_group="eng", oidc_approver_group="plan-approvers")
    client = OIDCClient(ISSUER, CLIENT_ID, CLIENT_SECRET, REDIRECT, transport=provider.transport())
    return create_app(cfg, oidc=client)


def sign_in_oidc(client: TestClient, provider: FakeProvider, next_path: str = "/#/projects/store", tamper_state: bool = False):
    r = client.get("/api/auth/login", params={"next": next_path}, follow_redirects=False)
    assert r.status_code == 302 and r.headers["location"].startswith(ISSUER + "/authorize?")
    assert "samesite=lax" in r.headers["set-cookie"].lower()
    code, state = provider.authorize(r.headers["location"])
    return client.get("/api/auth/callback", params={"code": code, "state": "forged" if tamper_state else state}, follow_redirects=False)


def test_oidc_sign_in(oidc_app, provider):
    client = TestClient(oidc_app)
    assert client.get("/api/auth/mode").json() == {"mode": "oidc"}
    assert client.get("/api/me").status_code == 401
    r = sign_in_oidc(client, provider)
    assert r.status_code == 302 and r.headers["location"] == "/#/projects/store"
    cookie = [c for c in r.headers.get_list("set-cookie") if c.startswith(COOKIE_NAME + "=")][0]
    assert "HttpOnly" in cookie and "samesite=strict" in cookie.lower()
    me = client.get("/api/me").json()
    assert me["mode"] == "oidc" and me["identity"] == {
        "name": "Ana Ruiz", "email": "ana@example.com", "roles": [PLANNER, APPROVER], "id": f"{ISSUER}|ana"}
    # The password login is not served in OIDC mode.
    assert client.post("/api/login", json={"password": PASSWORD}).status_code == 404


def test_no_provider_token_reaches_the_browser(oidc_app, provider):
    client = TestClient(oidc_app)
    responses = [sign_in_oidc(client, provider), client.get("/api/me"), client.post("/api/logout")]
    blobs = [r.text + "".join(f"{k}:{v}" for k, v in r.headers.items()) for r in responses]
    for token in provider.issued_tokens + ["provider-access-token"]:
        assert not any(token in b for b in blobs)


@pytest.mark.parametrize(("case", "reason"), [
    ("state", "unverified"), ("nonce", "unverified"), ("issuer", "unverified"), ("audience", "unverified"),
    ("expired", "unverified"), ("forged", "unverified"), ("no_role", "no_role"),
])
def test_refused_callbacks(oidc_app, provider, case, reason):
    client = TestClient(oidc_app)
    overrides = {
        "nonce": {"nonce": "another"}, "issuer": {"iss": "https://evil.example"}, "audience": {"aud": "someone-else"},
        "expired": {"exp": 1000}, "no_role": {"groups": ["sales"]},
    }
    provider.token_overrides = overrides.get(case, {})
    if case == "forged":
        provider.sign_with = RSAKey.generate_key(2048, parameters={"kid": "k1"})
    r = sign_in_oidc(client, provider, tamper_state=case == "state")
    assert r.status_code == 302 and r.headers["location"] == f"/#/signin?error={reason}"
    assert client.get("/api/me").status_code == 401


def test_an_expired_attempt_is_refused(oidc_app, provider):
    client = TestClient(oidc_app)
    r = client.get("/api/auth/login", follow_redirects=False)
    code, state = provider.authorize(r.headers["location"])
    client.cookies.clear()  # the attempt cookie expired
    r = client.get("/api/auth/callback", params={"code": code, "state": state}, follow_redirects=False)
    assert r.headers["location"] == "/#/signin?error=expired"


def test_rotated_keys_are_read_again(oidc_app, provider):
    client = TestClient(oidc_app)
    sign_in_oidc(client, provider)
    reads = provider.jwks_reads
    provider.rotate()
    client.post("/api/logout")
    client.cookies.clear()
    assert sign_in_oidc(client, provider).headers["location"] == "/#/projects/store"
    assert provider.jwks_reads == reads + 1


def test_a_redirect_to_another_site_lands_home(oidc_app, provider):
    client = TestClient(oidc_app)
    assert sign_in_oidc(client, provider, next_path="https://evil.example/").headers["location"] == "/"


def test_logout_ends_the_session_and_names_the_provider_logout(oidc_app, provider):
    client = TestClient(oidc_app)
    sign_in_oidc(client, provider)
    assert client.post("/api/logout").json() == {"signed_in": False, "end_session_url": ISSUER + "/logout"}
    assert client.get("/api/me").status_code == 401


def test_a_planner_gets_403_on_an_approver_route(oidc_app, provider):
    from fastapi import Depends

    oidc_app.add_api_route("/api/test-approver", lambda: {"ok": True}, dependencies=[Depends(oidc_app.state.require_role(APPROVER))])
    provider.claims["groups"] = ["eng"]
    client = TestClient(oidc_app)
    sign_in_oidc(client, provider)
    r = client.get("/api/test-approver")
    assert r.status_code == 403 and r.json()["error"]["code"] == "role_required"


# Local mode


def test_local_mode(config):
    client = TestClient(create_app(config))
    assert client.get("/api/auth/mode").json() == {"mode": "local"}
    sign_in(client)
    me = client.get("/api/me").json()
    assert me["mode"] == "local" and me["identity"]["roles"] == [PLANNER, APPROVER] and me["identity"]["id"] == "local|operator"
    assert client.get("/api/auth/login", follow_redirects=False).status_code == 404


def _serve_env(monkeypatch, **extra):
    for k, v in {**BASE_ENV, "WORKBENCH_PASSWORD_HASH": "scrypt$x", **extra}.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("WORKBENCH_OIDC_ISSUER", raising=False)


def test_serve_refuses_local_mode_off_loopback(monkeypatch, capsys):
    import uvicorn

    from workbench.cli import main

    ran = []
    monkeypatch.setattr(uvicorn, "run", lambda *a, **k: ran.append(k["host"]))
    _serve_env(monkeypatch)
    assert main(["serve", "--host", "0.0.0.0"]) == 2
    assert "WORKBENCH_OIDC_ISSUER" in capsys.readouterr().err and ran == []

    assert main(["serve", "--host", "127.0.0.1"]) == 0 and ran == ["127.0.0.1"]
    _serve_env(monkeypatch, WORKBENCH_ALLOW_LOCAL_MODE="1")
    assert main(["serve", "--host", "0.0.0.0"]) == 0 and ran[-1] == "0.0.0.0"


def test_a_refused_sign_in_ends_an_earlier_session(oidc_app, provider):
    """Found in the Dex check: a no-role sign-in left the earlier person signed in."""
    client = TestClient(oidc_app)
    sign_in_oidc(client, provider)
    assert client.get("/api/me").status_code == 200
    provider.claims["groups"] = ["sales"]
    r = sign_in_oidc(client, provider)
    assert r.headers["location"] == "/#/signin?error=no_role"
    assert client.get("/api/me").status_code == 401
