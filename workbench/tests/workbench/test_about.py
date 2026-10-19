from __future__ import annotations

from fastapi.testclient import TestClient

from tests.workbench.conftest import make_config
from workbench import config as config_module
from workbench.app import create_app
from workbench.config import SOURCE_URL, Config


def test_anyone_can_find_the_source_and_license(config):
    with TestClient(create_app(config)) as client:
        about = client.get("/api/about").json()
    assert about == {"name": "plan-workbench", "license": "AGPL-3.0-or-later", "source_url": SOURCE_URL}


def test_whoever_runs_a_modified_workbench_names_their_source(store):
    store.plan([])
    cfg = make_config(store.root, source_url="https://git.example.com/our/fork")
    with TestClient(create_app(cfg)) as client:
        assert client.get("/api/about").json()["source_url"] == "https://git.example.com/our/fork"


def test_the_source_url_comes_from_the_environment():
    env = {"WORKBENCH_SORTIE_URL": "http://sortie", "WORKBENCH_SECRET_KEY": "k", "WORKBENCH_PASSWORD_HASH": "h",
           "WORKBENCH_HOME": "/tmp/wb-home"}
    assert Config.from_env(env).source_url == SOURCE_URL
    assert Config.from_env({**env, "WORKBENCH_SOURCE_URL": " https://x.example/src "}).source_url == "https://x.example/src"


def test_a_wheel_uses_the_files_it_bundles(tmp_path, monkeypatch):
    # From a source checkout: the file in the source tree.
    assert config_module.bundled("prompts/planning-session.md", "prompts/planning-session.md").is_file()
    # From a wheel: the copy inside the package wins.
    package = tmp_path / "site-packages" / "workbench"
    (package / "prompts").mkdir(parents=True)
    (package / "prompts" / "planning-session.md").write_text("bundled")
    monkeypatch.setattr(config_module, "PACKAGE", package)
    assert config_module.bundled("prompts/planning-session.md", "prompts/planning-session.md").read_text() == "bundled"
