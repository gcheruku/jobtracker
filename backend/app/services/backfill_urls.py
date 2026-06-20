"""Recover / correct posting URLs on existing jobs.

Re-scans recent Job-alert emails, builds each job link's tile text, and matches
every job to a URL by title+company (the same content-based logic the live
ingest uses). Two modes:

  * default: only fill jobs that currently have no URL.
  * recompute: also re-derive URLs for jobs that already have one and overwrite
    when a confident match is found — used to fix earlier order-misassigned URLs.

Run:  python -m app.services.backfill_urls                 # fill missing, 7 days
      python -m app.services.backfill_urls 14 400          # days, max messages
      python -m app.services.backfill_urls 14 400 recompute  # also fix wrong URLs
"""
from __future__ import annotations

import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from ..config import GMAIL_LABEL
from ..database import engine
from ..logging_config import logger, setup_logging
from ..models import Job
from . import gmail_client as gm
from .email_parser import build_payload, match_tile


def _collect_links(days: int, max_messages: int):
    """Return {provider: [links]} (links carry tile text) from recent emails."""
    service = gm.get_service()
    label_id = gm.get_label_id(service, GMAIL_LABEL)
    if not label_id:
        raise RuntimeError(f"Gmail label '{GMAIL_LABEL}' not found")

    after = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp())
    msg_ids = gm.list_message_ids(service, label_id, after, max_messages)
    logger.info("Backfill: scanning %d recent emails (last %dd)", len(msg_ids), days)

    by_provider: dict[str, list] = defaultdict(list)
    for msg_id in msg_ids:
        payload = build_payload(gm.fetch_message(service, msg_id))
        by_provider[payload.provider].extend(payload.links)
    return by_provider


def backfill_urls(days: int = 7, max_messages: int = 200, recompute: bool = False) -> dict:
    by_provider = _collect_links(days, max_messages)
    all_links = [l for links in by_provider.values() for l in links]

    summary = {"considered": 0, "filled": 0, "corrected": 0, "unchanged": 0}
    with Session(engine) as session:
        rows = (
            session.exec(select(Job)).all()
            if recompute
            else session.exec(
                select(Job).where((Job.url == None) | (Job.url == ""))  # noqa: E711
            ).all()
        )
        # URLs already correctly in use, so we don't assign one to two jobs.
        used = {j.url for j in session.exec(select(Job)).all() if j.url}

        for job in rows:
            if not job.title or not job.company:
                continue
            summary["considered"] += 1
            candidates = by_provider.get(job.source or "", []) or all_links
            url = match_tile(job.title, job.company, candidates) or match_tile(
                job.title, job.company, all_links
            )
            if not url:
                summary["unchanged"] += 1
                continue
            if url == job.url:
                summary["unchanged"] += 1
                continue
            if url in used and url != job.url:
                # belongs to another job already; don't duplicate-assign
                summary["unchanged"] += 1
                continue
            had_url = bool(job.url)
            job.url = url
            used.add(url)
            session.add(job)
            summary["corrected" if had_url else "filled"] += 1
            logger.info(
                "%s URL for: %s @ %s",
                "Corrected" if had_url else "Filled",
                job.title,
                job.company,
            )
        session.commit()

    logger.info("Backfill complete: %s", summary)
    return summary


if __name__ == "__main__":
    setup_logging()
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    max_msgs = int(sys.argv[2]) if len(sys.argv) > 2 else 200
    recompute = len(sys.argv) > 3 and sys.argv[3].lower() == "recompute"
    print(backfill_urls(days=days, max_messages=max_msgs, recompute=recompute))
