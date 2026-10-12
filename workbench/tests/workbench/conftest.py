from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from workbench.auth import hash_password
from workbench.config import Config

PASSWORD = "correct horse"
SORTIE_TOKEN = "sortie-control-token-0123456789"
BROKER_TOKEN = "broker-viewer-token-9876543210"
_HASH = hash_password(PASSWORD)


def make_config(store: Path, **overrides) -> Config:
    values = dict(
        store=store, sortie_url="http://sortie.test", sortie_token=SORTIE_TOKEN,
        password_hash=_HASH, secret_key="test-secret", frontend_dir=None, debounce_ms=50, poll_seconds=0.2,
    )
    values.update(overrides)
    return Config(**values)


def sign_in(client: TestClient) -> None:
    r = client.post("/api/login", json={"password": PASSWORD})
    assert r.status_code == 200, r.text


@pytest.fixture
def config(store) -> Config:
    store.plan([])
    return make_config(store.root)
