"""The worker: every background job, in its own process (python -m app.worker).

The API no longer runs jobs, so scaling it no longer multiplies them, and the jobs keep running when the
API is idle or scaled to zero (the retention guarantee depends on that). Each job claims its rows
(app/jobs.py, the holding-reply claim, SKIP LOCKED embedding), so running several workers is safe.
"""

import asyncio
import logging
import signal
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from app import agent_client
from app.core import mailbox
from app.core.config import get_settings
from app.core.constants import EMBED_POLL_SECONDS, HOLDING_REPLY_POLL_SECONDS
from app.core.logging_setup import configure_logging
from app.dashboard import generate_pending
from app.holding_reply_scheduler import schedule_new, send_due
from app.rag.embedding_models import check_columns
from app.rag.ingest import embed_pending, embed_pending_locally
from app.retention import apply_retention
from app.send_reconciler import reconcile_sends
from app.vault_retention import RUN_EVERY

logger = logging.getLogger(__name__)

# How long running jobs get to finish after SIGTERM before they are abandoned (leases then expire).
SHUTDOWN_GRACE_SECONDS = 20
# Small batches keep the ~6-calls-per-email pipeline under the model's rate limit.
DRAFTS_PER_PASS = 2
RECONCILE_EVERY_SECONDS = 300


@dataclass(frozen=True)
class Job:
    name: str
    every: Callable[[], float]
    run: Callable[[], Awaitable[object]]


async def _holding_replies() -> None:
    await schedule_new()
    await send_due()


async def _embeddings() -> None:
    await embed_pending()
    await embed_pending_locally()


def jobs() -> list[Job]:
    settings = get_settings()
    found = [
        Job("embeddings", lambda: EMBED_POLL_SECONDS, _embeddings),
        Job("holding replies", lambda: HOLDING_REPLY_POLL_SECONDS, _holding_replies),
        Job("send reconciliation", lambda: RECONCILE_EVERY_SECONDS, reconcile_sends),
        Job("retention", lambda: RUN_EVERY.total_seconds(), apply_retention),
    ]
    if settings.auto_generate:
        found.append(Job("drafting", lambda: settings.generate_poll_seconds,
                         lambda: generate_pending(limit=DRAFTS_PER_PASS)))
    return found


async def _every(job: Job) -> None:
    """Run the job forever; a failed pass is logged and tried again next time."""
    while True:
        try:
            result = await job.run()
            if result:
                logger.info("%s: %s", job.name, result)
        except Exception:
            logger.exception("%s pass failed", job.name)
        await asyncio.sleep(job.every())


async def run() -> None:
    configure_logging()
    await check_columns()
    await mailbox.resolve_owner()
    stop = asyncio.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        asyncio.get_running_loop().add_signal_handler(sig, stop.set)
    tasks = [asyncio.create_task(_every(job), name=job.name) for job in jobs()]
    logger.info("worker running: %s", ", ".join(task.get_name() for task in tasks))
    await stop.wait()
    for task in tasks:
        task.cancel()
    # Awaited, not just cancelled: a job mid-send records its outcome, or its lease and claim expire.
    await asyncio.wait(tasks, timeout=SHUTDOWN_GRACE_SECONDS)
    await agent_client.close()


if __name__ == "__main__":
    asyncio.run(run())
