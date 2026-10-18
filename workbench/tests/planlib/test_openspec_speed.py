"""planlib's defaults for calling OpenSpec: no usage telemetry, and no
subprocess for a change whose files did not change. Both matter at every
approval: the workbench validates the whole plan each time."""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path

import pytest

import planlib
import planlib.requirements as req
from tests.conftest import breakdown, deliverable

CAPTURED = Path(__file__).parent.parent / "fixtures" / "openspec-1.13"
HAS_OPENSPEC = shutil.which("openspec") is not None


class FakeRun:
    """Stands in for subprocess.run: records each call's environment."""

    def __init__(self, output='{"deltas": []}', returncode=0):
        self.calls: list[dict] = []
        self.output, self.returncode = output, returncode

    def __call__(self, cmd, **kw):
        self.calls.append(kw)
        return subprocess.CompletedProcess(cmd, self.returncode, self.output, "boom")


def change(store, name="billing"):
    d = store.root / "openspec" / "changes" / name
    (d / "specs").mkdir(parents=True, exist_ok=True)
    (d / "proposal.md").write_text("## Why\n\nx\n")
    return d


def test_telemetry_is_off_by_default(store, monkeypatch):
    run = FakeRun()
    monkeypatch.setattr(req.subprocess, "run", run)
    monkeypatch.delenv("OPENSPEC_TELEMETRY", raising=False)
    monkeypatch.delenv("DO_NOT_TRACK", raising=False)
    change(store)
    req.openspec_show(store.root, "billing")
    env = run.calls[0]["env"]
    assert env["OPENSPEC_TELEMETRY"] == "0" and env["DO_NOT_TRACK"] == "1"
    assert env["PATH"]  # the rest of the environment is kept


def test_an_explicit_operator_setting_wins(store, monkeypatch):
    run = FakeRun()
    monkeypatch.setattr(req.subprocess, "run", run)
    monkeypatch.setenv("OPENSPEC_TELEMETRY", "1")
    change(store)
    req.openspec_show(store.root, "billing")
    assert run.calls[0]["env"]["OPENSPEC_TELEMETRY"] == "1"


def test_an_unchanged_change_runs_openspec_once(store, monkeypatch):
    run = FakeRun('{"deltas": [{"spec": "a"}]}')
    monkeypatch.setattr(req.subprocess, "run", run)
    d = change(store)
    first = req.openspec_show(store.root, "billing")
    first["deltas"].clear()  # a caller changing its copy must not change the cache
    assert req.openspec_show(store.root, "billing") == {"deltas": [{"spec": "a"}]}
    assert len(run.calls) == 1
    (d / "specs" / "new.md").write_text("x")
    req.openspec_show(store.root, "billing")
    assert len(run.calls) == 2
    (store.root / "openspec" / "config.yaml").write_text("schema: other\n")
    req.openspec_show(store.root, "billing")
    assert len(run.calls) == 3


def test_a_failure_is_not_cached(store, monkeypatch):
    run = FakeRun(returncode=1)
    monkeypatch.setattr(req.subprocess, "run", run)
    change(store)
    for _ in range(2):
        with pytest.raises(req.RequirementsError):
            req.openspec_show(store.root, "billing")
    assert len(run.calls) == 2


def test_approving_again_costs_no_openspec_call(store, monkeypatch):
    """What the workbench does at each approval: validate with new approvals,
    files unchanged."""
    shutil.copytree(CAPTURED / "billing", store.root / "openspec" / "changes" / "billing", dirs_exist_ok=True)
    store.plan([("billing", [])])
    store.change("billing", breakdown(deliverable("a", covers=["billing/invoicing#Monthly invoice"])))
    run = FakeRun((CAPTURED / "billing.show.json").read_text())
    monkeypatch.setattr(req.subprocess, "run", run)
    first = planlib.validate(store.root)
    assert first.errors == [] and first.graph is not None
    result = planlib.validate(store.root, approvals={"billing/a": "sha256:x"})
    assert result.errors == [] and len(run.calls) == 1


@pytest.mark.skipif(not HAS_OPENSPEC, reason="openspec not installed")
def test_real_openspec_second_check_is_fast(store):
    shutil.copytree(CAPTURED / "billing", store.root / "openspec" / "changes" / "billing", dirs_exist_ok=True)
    (store.root / "openspec" / "config.yaml").write_text("schema: spec-driven\n")
    req.openspec_show(store.root, "billing")
    t = time.monotonic()
    req.openspec_show(store.root, "billing")
    assert time.monotonic() - t < 0.05


def test_the_planning_agent_runs_openspec_without_telemetry(tmp_path, monkeypatch):
    import asyncio

    import workbench.sessions as sessions

    seen = {}

    class Stop(Exception):
        pass

    def fake_popen(cmd, **kw):
        seen.update(kw["env"])
        raise Stop

    monkeypatch.setattr(sessions.subprocess, "Popen", fake_popen)
    monkeypatch.delenv("OPENSPEC_TELEMETRY", raising=False)
    store = tmp_path / "store"
    store.mkdir()
    m = sessions.SessionManager(store, ["acp-broker"], ["agent"], None, runtime_dir=tmp_path / "rt")
    with pytest.raises(Stop):
        asyncio.run(m.start("plan this"))
    asyncio.run(m.aclose())
    assert seen["OPENSPEC_TELEMETRY"] == "0" and seen["DO_NOT_TRACK"] == "1"
