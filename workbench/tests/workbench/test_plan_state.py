"""PlanState and the hub's poll, driven directly: no file watcher, no timing."""

from __future__ import annotations

import asyncio
import threading

from tests.conftest import breakdown, deliverable
from tests.workbench.fake_sortie import FakeSortie
from tests.workbench.test_watch import validate_offline
from workbench.hub import Hub
from workbench.plan_state import PlanState


def keys(state):
    return {n["plan_key"] for n in state.graph["nodes"]}


def test_a_poll_picks_up_an_edit_the_watcher_missed(store):
    store.plan([("billing", [])])
    store.change("billing", breakdown(deliverable("invoice")))
    state = PlanState(store.root, validate_offline)
    state.refresh()
    assert not state.stale()
    hub = Hub(state, FakeSortie().client().bind("T"))

    # A new change directory and the files in it: the edit inotify can lose,
    # because the files land before the watch on the new directory exists.
    store.plan([("billing", []), ("welcome", [])])
    store.change("welcome", breakdown(deliverable("greet")))
    assert state.stale()

    asyncio.run(hub.poll_once())
    assert keys(state) == {"billing", "billing/invoice", "welcome", "welcome/greet"}
    assert not state.stale()


def test_a_slow_refresh_cannot_undo_a_newer_one(store):
    store.plan([("billing", [])])
    store.change("billing", breakdown(deliverable("invoice")))
    first_entered, release = threading.Event(), threading.Event()
    calls = []

    def validate(root, **kw):
        calls.append(None)
        if len(calls) == 1:
            # Read the store before the edit, then stall.
            result = validate_offline(root, **kw)
            first_entered.set()
            release.wait()
            return result
        return validate_offline(root, **kw)

    state = PlanState(store.root, validate)
    slow = threading.Thread(target=state.refresh)
    slow.start()
    first_entered.wait()
    store.change("billing", breakdown(deliverable("invoice"), deliverable("tax")))
    fresh = threading.Thread(target=state.refresh)
    fresh.start()
    # Without the lock the fresh refresh finishes here, and the slow one then
    # overwrites it. With the lock it waits; either way, this never fails a
    # correct implementation.
    fresh.join(timeout=0.2)
    release.set()
    slow.join()
    fresh.join()
    assert keys(state) == {"billing", "billing/invoice", "billing/tax"}
