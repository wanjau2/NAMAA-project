"""Background workers for extraction progress and outbox compensation."""

from __future__ import annotations

import asyncio
import logging
import uuid

from app.config import get_settings
from app.db import SessionLocal
from app.services.extractions import (
    TERMINAL,
    advance_job,
    claim_queued_jobs,
    proposals_for_job,
    publish_job,
)
from app.services.outbox import claim_due_entries, process_entry

logger = logging.getLogger("namaa.workers")


class WorkerRuntime:
    def __init__(self) -> None:
        self.worker_id = f"worker-{uuid.uuid4().hex[:8]}"
        self._tasks: list[asyncio.Task] = []
        self._stop = asyncio.Event()

    async def start(self) -> None:
        self._stop.clear()
        self._tasks = [
            asyncio.create_task(self._extraction_loop(), name="extraction-worker"),
            asyncio.create_task(self._outbox_loop(), name="outbox-worker"),
        ]
        logger.info("Workers started id=%s", self.worker_id)

    async def stop(self) -> None:
        self._stop.set()
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        logger.info("Workers stopped id=%s", self.worker_id)

    async def _extraction_loop(self) -> None:
        settings = get_settings()
        poll = settings.extraction_worker_poll_ms / 1000.0
        while not self._stop.is_set():
            try:
                await self._tick_extractions()
            except Exception:  # noqa: BLE001 — worker must not die silently
                logger.exception("Extraction worker tick failed")
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=poll)
            except TimeoutError:
                continue

    async def _outbox_loop(self) -> None:
        settings = get_settings()
        poll = settings.outbox_worker_poll_ms / 1000.0
        while not self._stop.is_set():
            try:
                await self._tick_outbox()
            except Exception:  # noqa: BLE001
                logger.exception("Outbox worker tick failed")
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=poll)
            except TimeoutError:
                continue

    async def _tick_extractions(self) -> None:
        db = SessionLocal()
        try:
            jobs = claim_queued_jobs(db, worker_id=self.worker_id)
            for job in jobs:
                await publish_job(job)
                # Simulate multi-step progress without hammering DB every 100ms.
                while job.state not in TERMINAL:
                    await asyncio.sleep(0.35)
                    job = advance_job(db, job)
                    props = proposals_for_job(db, job) if job.state == "succeeded" else None
                    await publish_job(job, proposals=props)
                    if job.state in TERMINAL:
                        break
                    # Sparse DB already updated inside advance_job; SSE carries the rest.
        finally:
            db.close()

    async def _tick_outbox(self) -> None:
        db = SessionLocal()
        try:
            entries = claim_due_entries(db, worker_id=self.worker_id)
            db.commit()
            for entry in entries:
                process_entry(db, entry)
                db.commit()
        finally:
            db.close()


runtime = WorkerRuntime()
