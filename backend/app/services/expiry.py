"""Sweep the Saved column and move lapsed postings to the Expired state.

Shared by the `expire_saved_jobs.py` CLI and the in-process scheduler so both
use one definition of "gone". A posting is moved to Expired when its live page
either shows an expiry banner (`fetch_jd_info(...).expired`) or 404/410s
(`.not_found`). A bot wall (403/429 or a 200 challenge page) or any fetch error
leaves the job untouched — the sweep only ever *under*-expires, never moving a
job it couldn't positively confirm is gone.

Scope mirrors the dashboard's Saved column exactly (`_is_saved`: display status
"Saved", not skipped, not mismatched), and additionally excludes starred
(watchlist) jobs so anything you flagged to revisit is never swept out.
"""
from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from typing import Callable, Optional

from sqlmodel import Session, select

from ..logging_config import logger
from ..models import Job
from .jd_fetch import fetch_jd_info
from .semantic import _is_saved

# A manual CLI run and the scheduled run must not fetch/commit concurrently.
_sweep_lock = threading.Lock()

# Per-job callback: (index, total, outcome, label) where outcome is one of
# "gone" | "expired" | "active" | "no_url". Lets the CLI print live progress
# while the scheduler stays quiet and just logs a summary.
ProgressFn = Callable[[int, int, str, str], None]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def saved_not_starred(session: Session) -> list[Job]:
    """Jobs in the Saved column on the dashboard, excluding starred ones,
    most-recent-first so a `limit` checks the freshest postings."""
    jobs = [j for j in session.exec(select(Job)).all() if _is_saved(j) and not j.watchlist]
    jobs.sort(key=lambda j: (j.email_date or j.status_updated_at or ""), reverse=True)
    return jobs


def sweep_expired_saved(
    session: Session,
    *,
    dry_run: bool = False,
    limit: Optional[int] = None,
    delay: float = 1.0,
    progress: Optional[ProgressFn] = None,
) -> dict:
    """Check each Saved (non-starred) posting live and move the gone ones to
    Expired. Returns a summary dict. Non-overlapping: if a sweep is already
    running this returns immediately with ``{"skipped": True}``."""
    if not _sweep_lock.acquire(blocking=False):
        logger.info("Expiry sweep already running; skipping this trigger")
        return {"skipped": True}
    try:
        jobs = saved_not_starred(session)
        if limit is not None:
            jobs = jobs[:limit]
        total = len(jobs)

        expired = gone = no_url = checked = 0
        for i, job in enumerate(jobs, 1):
            label = f"{(job.title or '?')[:50]} — {(job.company or '?')[:30]}"
            if not job.url:
                no_url += 1
                if progress:
                    progress(i, total, "no_url", label)
                continue

            checked += 1
            try:
                result = fetch_jd_info(job.url)
            except Exception as exc:  # never let one bad page abort the sweep
                logger.warning("Expiry sweep fetch failed for %s: %s", job.job_key, exc)
                if progress:
                    progress(i, total, "active", label)
                continue

            # Expiry banner and a 404/410 both mean the posting is gone; either
            # moves it to Expired. A bot wall / error carries neither flag and
            # is left active, so an IP block is never read as a dead posting.
            if result.expired or result.not_found:
                if result.not_found:
                    gone += 1
                    outcome = "gone"
                else:
                    expired += 1
                    outcome = "expired"
                if not dry_run:
                    job.status = "Expired"  # off-board; surfaces in the Inactive view
                    job.status_updated_at = _now()
                    # Save a freshly fetched JD only when the row lacked one.
                    if result.description and not (job.job_description or "").strip():
                        job.job_description = result.description
                    session.add(job)
                    session.commit()
                if progress:
                    progress(i, total, outcome, label)
            else:
                if progress:
                    progress(i, total, "active", label)

            if delay and i < total:
                time.sleep(delay)

        moved = expired + gone
        summary = {
            "skipped": False,
            "total": total,
            "checked": checked,
            "expired": expired,
            "gone": gone,
            "moved": moved,
            "active": checked - moved,
            "no_url": no_url,
            "dry_run": dry_run,
        }
        logger.info(
            "Expiry sweep %s: %d moved (%d banner, %d 404), %d active, %d no-url of %d",
            "(dry run)" if dry_run else "done",
            moved, expired, gone, summary["active"], no_url, total,
        )
        return summary
    finally:
        _sweep_lock.release()
