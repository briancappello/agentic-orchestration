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
