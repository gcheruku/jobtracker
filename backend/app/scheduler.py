"""APScheduler that runs the Gmail ingest every INGEST_INTERVAL_HOURS.

In-process scheduler: it runs while the API server is up, which suits a
self-hosted single-process deployment. (For always-on scheduling independent of
the web process, run `python -m app.ingest_cron` from an OS cron instead.)
"""
from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler
from sqlmodel import Session

from .config import (
    EXPIRY_SWEEP_DELAY_S,
    EXPIRY_SWEEP_ENABLED,
    EXPIRY_SWEEP_INTERVAL_HOURS,
    INGEST_INTERVAL_HOURS,
    INGEST_RUN_ON_STARTUP,
)
from .logging_config import logger
from .services.ingest import run_ingest

_scheduler: BackgroundScheduler | None = None


def _job() -> None:
    logger.info("Scheduled ingest triggered")
    run_ingest()


def _expiry_job() -> None:
    logger.info("Scheduled expiry sweep triggered")
    # Imported lazily and given its own session so this never touches the request
    # path. sweep_expired_saved is self-locking, so an overrun is a no-op.
    from .database import engine
    from .services.expiry import sweep_expired_saved

    with Session(engine) as session:
        sweep_expired_saved(session, delay=EXPIRY_SWEEP_DELAY_S)


def start_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        return
    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(
        _job,
        "interval",
        hours=INGEST_INTERVAL_HOURS,
        id="gmail_ingest",
        max_instances=1,
        coalesce=True,
    )
    if EXPIRY_SWEEP_ENABLED:
        _scheduler.add_job(
            _expiry_job,
            "interval",
            hours=EXPIRY_SWEEP_INTERVAL_HOURS,
            id="expiry_sweep",
            max_instances=1,  # never overlap a long sweep with the next tick
            coalesce=True,
        )
    _scheduler.start()
    logger.info("Scheduler started: ingest every %.1fh", INGEST_INTERVAL_HOURS)
    if EXPIRY_SWEEP_ENABLED:
        logger.info("Expiry sweep scheduled every %.1fh", EXPIRY_SWEEP_INTERVAL_HOURS)
    if INGEST_RUN_ON_STARTUP:
        _scheduler.add_job(_job, id="gmail_ingest_startup")


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
