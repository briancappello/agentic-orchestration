from __future__ import annotations

from fastapi.testclient import TestClient

from tests.workbench.fake_sortie import FakeSortie
from tests.workbench.test_approvals import app_for, billing, status
from tests.workbench.conftest import sign_in


def running(fake, key, **rt):
    return fake.issue(key, runtime={"status": "running", "turn_count": 3, "last_message": "hi", "attempt": None, **rt})


def test_a_running_worker_joins_its_story(store):
    billing(store)
    fake = FakeSortie()
    b1 = running(fake, "billing/b1")
    fake.issue("billing/b2", runtime={"status": "retrying", "attempt": 2, "turn_count": None, "last_message": None})
    fake.run(b1["identifier"], "s1", stage="implement", broker="http://broker-1.test", held=True, holder="human")
    fake.retrying["T-2"] = {"issue_identifier": "T-2", "attempt": 2}
    app = app_for(store, fake)
    with TestClient(app) as client:
        sign_in(client)
        polled(app, b1["identifier"])
        rt = status(app, "billing/b1")["runtime"]
        assert rt["status"] == "running" and rt["turn_count"] == 3
        assert rt["stage"] == "implement" and rt["session_id"] == "s1" and rt["watchable"] is True
        assert rt["held"] is True and rt["holder"] == "human"
        rt2 = status(app, "billing/b2")["runtime"]
        assert rt2["status"] == "retrying" and rt2["attempt"] == 2 and rt2["watchable"] is False and rt2["stage"] is None


def test_a_worker_whose_broker_did_not_report_cannot_be_watched(store):
    billing(store)
    fake = FakeSortie()
    b1 = running(fake, "billing/b1")
    fake.run(b1["identifier"], "s1")
    app = app_for(store, fake)
    with TestClient(app) as client:
        sign_in(client)
        polled(app, b1["identifier"])
        assert status(app, "billing/b1")["runtime"]["watchable"] is False


def test_a_failed_state_read_keeps_the_runtime(store):
    billing(store)
    fake = FakeSortie()
    b1 = running(fake, "billing/b1")
    fake.run(b1["identifier"], "s1", broker="http://broker-1.test")
    fake.state_down = True
    app = app_for(store, fake)
    with TestClient(app) as client:
        sign_in(client)
        polled(app, b1["identifier"])
        rt = status(app, "billing/b1")["runtime"]
        assert rt["status"] == "running" and rt["watchable"] is False and rt["stage"] is None
        assert ("GET", "/api/v1/state", None) in fake.requests


def test_no_state_read_without_a_runtime(store):
    billing(store)
    fake = FakeSortie()
    fake.issue("billing/b1")
    app = app_for(store, fake)
    with TestClient(app) as client:
        sign_in(client)
        assert status(app, "billing/b1")["runtime"] is None
        assert not any(path == "/api/v1/state" for _, path, _ in fake.requests)


# The relay, against a fake Sortie and fake brokers.

import json

import httpx

from tests.workbench.conftest import P, make_config, project
from tests.workbench.fake_oidc import CLIENT_ID, CLIENT_SECRET, ISSUER, REDIRECT, FakeProvider
from tests.workbench.test_identity import sign_in_oidc
from tests.workbench.test_watch import validate_offline
from workbench.app import create_app
from workbench.oidc import OIDCClient

TOKEN = "viewer-secret-1"


class FakeBrokers:
    """Brokers by host. Each serves its events once, then closes the stream,
    as a broker does when its run ends; ``after`` runs when it has."""

    def __init__(self):
        self.brokers: dict[str, dict] = {}
        self.commands: list[tuple[str, dict]] = []
        self.last_event_ids: list[tuple[str, str | None]] = []

    def add(self, host, token, events, after=None):
        self.brokers[host] = {"token": token, "events": events, "after": after}
        return f"http://{host}"

    def transport(self):
        return httpx.MockTransport(self.handle)

    def handle(self, request: httpx.Request) -> httpx.Response:
        b = self.brokers.get(request.url.host)
        if b is None:
            return httpx.Response(404)
        if request.headers.get("authorization") != f"Bearer {b['token']}":
            return httpx.Response(401, json={"error": "token"})
        if request.url.path == "/commands":
            self.commands.append((request.url.host, json.loads(request.content)))
            return httpx.Response(200, json={"ok": True})
        if request.url.path == "/events":
            self.last_event_ids.append((request.url.host, request.headers.get("last-event-id")))
            body = "".join(f"id: {e['seq']}\ndata: {json.dumps(e)}\n\n" for e in b["events"])
            if b["after"]:
                b["after"]()
            return httpx.Response(200, content=body.encode(), headers={"content-type": "text/event-stream"})
        return httpx.Response(404)


def update(seq, text):
    return {"seq": seq, "time": "2026-10-17T00:00:00Z", "type": "update",
            "update": {"update": {"sessionUpdate": "agent_message_chunk", "content": {"text": text}}}}


def worker_app(store, fake, brokers, **services):
    billing(store)
    b1 = running(fake, "billing/b1")
    fake.run(b1["identifier"], "s1", broker=brokers.add("broker-1.test", TOKEN, [update(1, "hello")]), token=TOKEN)
    return create_app(make_config(store.root, **services.pop("cfg", {})), validate=validate_offline, sortie=fake.client(),
                      broker_transport=brokers.transport(), **services), b1["identifier"]


def polled(app, ident):
    """Wait for the hub's first Sortie poll: until then no story carries its
    tracker identifier, and the worker routes answer 404."""
    from tests.workbench.test_watch import wait_for
    assert wait_for(lambda: any((n.get("tracker") or {}).get("identifier") == ident
                                for n in project(app).hub.doc.get("nodes") or [])), "no Sortie poll yet"


def sse_events(text):
    out = []
    for block in text.strip().split("\n\n"):
        ev = {"event": "message"}
        for line in block.splitlines():
            k, _, v = line.partition(": ")
            ev[k] = v
        out.append(ev)
    return out


def test_an_approver_steers_and_the_command_is_recorded(store):
    fake, brokers = FakeSortie(), FakeBrokers()
    app, ident = worker_app(store, fake, brokers)
    with TestClient(app) as client:
        sign_in(client)
        polled(app, ident)
        r = client.post(f"{P}/workers/{ident}/commands", json={"op": "steer", "text": "use the invoice table"})
        assert r.status_code == 200 and r.json()["recorded"]["actor_name"] == "Local operator"
        assert brokers.commands == [("broker-1.test", {"op": "steer", "text": "use the invoice table"})]
        msgs = client.get(f"{P}/workers/{ident}/messages").json()["commands"]
        assert [(m["op"], m["text"], m["actor_name"], m["session_id"]) for m in msgs] == [
            ("steer", "use the invoice table", "Local operator", "s1")]
        assert client.post(f"{P}/workers/{ident}/commands", json={"op": "launch"}).status_code == 400


def test_a_planner_watches_but_cannot_steer(store):
    fake, brokers = FakeSortie(), FakeBrokers()
    provider = FakeProvider()
    provider.claims["groups"] = ["eng"]
    cfg = dict(password_hash="", oidc_issuer=ISSUER, oidc_client_id=CLIENT_ID, oidc_client_secret=CLIENT_SECRET,
               oidc_redirect_url=REDIRECT, oidc_planner_group="eng", oidc_approver_group="plan-approvers")
    app, ident = worker_app(store, fake, brokers, cfg=cfg,
                            oidc=OIDCClient(ISSUER, CLIENT_ID, CLIENT_SECRET, REDIRECT, transport=provider.transport()))
    with TestClient(app) as client:
        sign_in_oidc(client, provider)
        polled(app, ident)
        project(app).workers.follow_poll = 0.01
        fake.end(ident)  # one run, then nothing: the stream ends
        fake.run(ident, "s1", broker="http://broker-1.test", token=TOKEN)
        brokers.brokers["broker-1.test"]["after"] = lambda: fake.end(ident)
        for op in ("steer", "prompt", "interrupt", "handback", "permit"):
            r = client.post(f"{P}/workers/{ident}/commands", json={"op": op, "text": "x"})
            assert r.status_code == 403 and r.json()["error"]["code"] == "role_required", op
        assert brokers.commands == []
        assert client.post(f"{P}/workers/{ident}/commands", json={"op": "state"}).status_code == 200
        assert "hello" in client.get(f"{P}/workers/{ident}/events").text
        assert client.get(f"{P}/workers/{ident}/messages").json()["commands"] == []


def test_an_unknown_worker_is_refused_before_sortie(store):
    fake, brokers = FakeSortie(), FakeBrokers()
    app, ident = worker_app(store, fake, brokers)
    with TestClient(app) as client:
        sign_in(client)
        polled(app, ident)
        before = len(fake.requests)
        for method, path in [("GET", "events"), ("GET", "messages"), ("POST", "commands")]:
            r = client.request(method, f"{P}/workers/OTHER-9/{path}", json={"op": "state"} if method == "POST" else None)
            assert r.status_code == 404 and r.json()["error"]["code"] == "worker_not_found"
        assert not any("OTHER-9" in path for _, path, _ in fake.requests[before:])


def test_the_stream_follows_the_story_and_ends(store):
    fake, brokers = FakeSortie(), FakeBrokers()
    app, ident = worker_app(store, fake, brokers)

    def second_run():
        fake.end(ident, retry_attempt=2)
        fake.run(ident, "s2", stage="review", broker=brokers.add("broker-2.test", "viewer-secret-2", [update(1, "again")],
                                                                    after=lambda: fake.end(ident)), token="viewer-secret-2")

    brokers.brokers["broker-1.test"]["after"] = second_run
    with TestClient(app) as client:
        sign_in(client)
        polled(app, ident)
        project(app).workers.follow_poll = 0.01
        r = client.get(f"{P}/workers/{ident}/events", headers={"Last-Event-ID": "7"})
        evs = sse_events(r.text)
        assert [(e["event"], e.get("id")) for e in evs] == [
            ("run", None), ("message", "1"), ("run", "0"), ("message", "1"), ("ended", None)]
        assert json.loads(evs[0]["data"]) == {"identifier": ident, "session_id": "s1", "stage": "implement", "follow": False}
        assert json.loads(evs[2]["data"]) == {"identifier": ident, "session_id": "s2", "stage": "review", "follow": True}
        assert "again" in evs[3]["data"]
        # Only the first run's broker gets the browser's Last-Event-ID.
        assert brokers.last_event_ids == [("broker-1.test", "7"), ("broker-2.test", None)]


def test_no_broker_token_or_address_reaches_the_browser(store):
    fake, brokers = FakeSortie(), FakeBrokers()
    app, ident = worker_app(store, fake, brokers)
    brokers.brokers["broker-1.test"]["after"] = lambda: fake.end(ident)
    with TestClient(app) as client:
        sign_in(client)
        polled(app, ident)
        project(app).workers.follow_poll = 0.01
        bodies = [client.post(f"{P}/workers/{ident}/commands", json={"op": "steer", "text": "go"}).text,
                  client.get(f"{P}/workers/{ident}/messages").text,
                  client.get(f"{P}/graph").text,
                  client.get(f"{P}/workers/{ident}/events").text]
        for body in bodies:
            assert TOKEN not in body and "broker-1.test" not in body


def test_a_worker_without_a_broker_answers_409(store):
    fake, brokers = FakeSortie(), FakeBrokers()
    app, ident = worker_app(store, fake, brokers)
    with TestClient(app) as client:
        sign_in(client)
        polled(app, ident)
        fake.brokers.pop(ident)
        r = client.post(f"{P}/workers/{ident}/commands", json={"op": "steer", "text": "x"})
        assert r.status_code == 409 and r.json()["error"]["code"] == "no_worker"
