"""The worker (app/worker.py): every background job, apart from the API."""

import asyncio

import pytest

from app import worker
from app.main import _lifespan


def test_the_worker_runs_every_job_and_drafting_only_when_switched_on(test_settings, monkeypatch):
    assert {job.name for job in worker.jobs()} == {"requested drafts", "embeddings", "categories", "holding replies",
                                                   "scheduled sends",
                                                   "send reconciliation", "retention", "drafting"}
    monkeypatch.setenv("AUTO_GENERATE", "false")
    from app.core.config import get_settings

    get_settings.cache_clear()
    names = {job.name for job in worker.jobs()}
    # Proactive drafting stops; the drafts people opened and are waiting on still come.
    assert "drafting" not in names and "requested drafts" in names


def test_a_failed_pass_is_logged_and_the_job_keeps_running(monkeypatch):
    runs = []

    async def flaky():
        runs.append(1)
        if len(runs) == 1:
            raise RuntimeError("database blip")
        raise asyncio.CancelledError

    async def no_wait(_seconds):
        return None

    monkeypatch.setattr(worker.asyncio, "sleep", no_wait)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(worker._every(worker.Job("flaky", lambda: 0, flaky)))
    assert len(runs) == 2


def test_the_api_starts_no_background_jobs(monkeypatch):
    started = []
    monkeypatch.setattr(asyncio, "create_task", lambda *a, **k: started.append(a))

    async def columns_fine():
        return None

    # The column check is database I/O, not a background job; it must not depend on what answers on :5432.
    monkeypatch.setattr("app.main.check_columns", columns_fine)

    async def run():
        async with _lifespan(None):
            pass

    asyncio.run(run())
    assert started == []


def test_sharing_a_process_the_jobs_run_until_told_to_stop_then_finish(monkeypatch):
    passes = []

    async def tick():
        passes.append(1)

    monkeypatch.setattr(worker, "jobs", lambda: [worker.Job("tick", lambda: 0.01, tick)])

    async def scenario():
        stop = asyncio.Event()
        running = asyncio.create_task(worker.run_until(stop))
        await asyncio.sleep(0.05)
        stop.set()
        await asyncio.wait_for(running, timeout=2)
        return len(passes)

    assert asyncio.run(scenario()) >= 2
