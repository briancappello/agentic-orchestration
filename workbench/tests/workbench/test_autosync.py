"""The sync loop on its own: debounce, coalescing, retry (workbench-auto-sync D1, D2)."""

from __future__ import annotations

import asyncio

from workbench.autosync import SyncFailure, SyncLoop


async def until(predicate, timeout=2.0):
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        if predicate():
            return True
        await asyncio.sleep(0.005)
    return predicate()


def run(scenario):
    async def main():
        stop = asyncio.Event()
        loops = []

        def make(run_once, **kw):
            loop = SyncLoop(run_once, **{"debounce": 0.02, "first_backoff": 0.02, "max_backoff": 0.08, **kw})
            loop.bind(asyncio.get_running_loop())
            loops.append(asyncio.create_task(loop.run(stop)))
            return loop

        try:
            await scenario(make)
        finally:
            stop.set()
            for t in loops:
                t.cancel()
            await asyncio.gather(*loops, return_exceptions=True)

    asyncio.run(main())


def test_three_triggers_during_a_run_cause_exactly_one_more():
    async def scenario(make):
        gate = asyncio.Event()
        runs = []

        async def once():
            runs.append(len(runs))
            if len(runs) == 1:
                await gate.wait()
            return {}

        loop = make(once)
        loop.trigger()
        assert await until(lambda: len(runs) == 1)
        assert loop.status()["state"] == "syncing"
        for _ in range(3):
            loop.trigger()
        gate.set()
        assert await until(lambda: len(runs) == 2)
        await asyncio.sleep(0.15)
        assert len(runs) == 2
        assert loop.status()["state"] == "synced"

    run(scenario)


def test_a_burst_of_triggers_folds_into_one_sync():
    async def scenario(make):
        runs = []

        async def once():
            runs.append(1)
            return {}

        loop = make(once, debounce=0.05)
        for _ in range(5):
            loop.trigger()
            await asyncio.sleep(0.005)
        await asyncio.sleep(0.2)
        assert len(runs) == 1

    run(scenario)


def test_a_failed_sync_is_retried_with_backoff_until_it_succeeds():
    async def scenario(make):
        seen = []

        async def once():
            seen.append(1)
            if len(seen) < 3:
                raise SyncFailure("sortie_unreachable", "cannot reach Sortie")
            return {"released": []}

        loop = make(once)
        loop.trigger()
        assert await until(lambda: loop.status()["state"] == "failed")
        assert loop.status()["reason"] == {"code": "sortie_unreachable", "message": "cannot reach Sortie"}
        assert loop.status()["retry_at"] is not None
        assert await until(lambda: loop.status()["state"] == "synced")
        assert len(seen) == 3
        status = loop.status()
        assert status["reason"] is None and status["retry_at"] is None and status["synced_at"] is not None

    run(scenario)


def test_backoff_never_exceeds_its_ceiling():
    async def scenario(make):
        times = []

        async def once():
            times.append(asyncio.get_running_loop().time())
            raise SyncFailure("sortie_unreachable", "down")

        loop = make(once, first_backoff=0.01, max_backoff=0.04)
        loop.trigger()
        assert await until(lambda: len(times) >= 6, timeout=3)
        gaps = [b - a for a, b in zip(times, times[1:])]
        assert max(gaps[2:]) < 0.04 + 0.05

    run(scenario)


def test_a_failure_that_needs_a_person_waits_for_the_next_trigger():
    async def scenario(make):
        seen = []

        async def once():
            seen.append(1)
            raise SyncFailure("plan_invalid", "fix the plan", retry=False)

        loop = make(once)
        loop.trigger()
        assert await until(lambda: loop.status()["state"] == "failed")
        await asyncio.sleep(0.2)
        assert len(seen) == 1 and loop.status()["retry_at"] is None
        loop.trigger()
        assert await until(lambda: len(seen) == 2)

    run(scenario)


def test_an_unexpected_error_fails_the_sync_and_is_retried():
    async def scenario(make):
        seen = []

        async def once():
            seen.append(1)
            if len(seen) == 1:
                raise RuntimeError("boom")
            return {}

        loop = make(once)
        loop.trigger()
        assert await until(lambda: loop.status()["state"] == "synced")
        assert len(seen) == 2

    run(scenario)


def test_status_changes_are_reported():
    async def scenario(make):
        states = []

        async def once():
            return {"released": [{"plan_key": "b/b1"}]}

        loop = make(once)
        loop.on_status(lambda s: states.append(s["state"]))
        loop.trigger()
        assert await until(lambda: states[-1:] == ["synced"])
        assert states == ["syncing", "synced"]
        assert loop.status()["result"] == {"released": [{"plan_key": "b/b1"}]}

    run(scenario)
