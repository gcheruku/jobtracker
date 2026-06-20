"""One-time backfill: recover missing posting URLs on existing jobs.

For jobs already in the DB without a `url`, re-scan recent Job-alert emails,
collect their candidate links, and match each URL-less job to a link by title
(same logic the live ingest now uses). Glassdoor alerts are image-based with no
title anchors, so those generally can't be recovered — this mostly helps
LinkedIn/Indeed/Dice rows.

Run:  python -m app.services.backfill_urls            # default: last 7 days
      python -m app.services.backfill_urls 14 300     # days, max messages
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
from .email_parser import build_payload, match_link, norm


def _collect_links(days: int, max_messages: int):
    """Return {provider: [links]} gathered from recent Job-alert emails."""
    service = gm.get_service()
    label_id = gm.get_label_id(service, GMAIL_LABEL)
    if not label_id:
        raise RuntimeError(f"Gmail label '{GMAIL_LABEL}' not found")

    after = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp())
    msg_ids = gm.list_message_ids(service, label_id, after, max_messages)
    logger.info("Backfill: scanning %d recent emails (last %dd)", len(msg_ids), days)

    links_by_provider: dict[str, list] = defaultdict(list)
    for msg_id in msg_ids:
        payload = build_payload(gm.fetch_message(service, msg_id))
        links_by_provider[payload.provider].extend(payload.links)
    return links_by_provider


def backfill_urls(days: int = 7, max_messages: int = 200) -> dict:
    links_by_provider = _collect_links(days, max_messages)
    all_links = [l for links in links_by_provider.values() for l in links]

    summary = {"url_less_rows": 0, "updated": 0, "skipped_no_match": 0}
    with Session(engine) as session:
        # URLs already in use, so we never assign a link to two different jobs.
        used_urls = {
            u[0]
            for u in session.exec(
                select(Job.url).where(Job.url.is_not(None))  # type: ignore[union-attr]
            ).all()
            if u and u[0]
        }

        url_less = session.exec(
            select(Job).where((Job.url == None) | (Job.url == ""))  # noqa: E711
        ).all()

        for job in url_less:
            if not job.title:
                continue
            summary["url_less_rows"] += 1
            # Prefer links from the same provider, fall back to all links.
            candidates = links_by_provider.get(job.source or "", []) or all_links
            url = match_link(job.title, candidates) or match_link(job.title, all_links)
            if url and url not in used_urls:
                job.url = url
                used_urls.add(url)
                session.add(job)
                summary["updated"] += 1
                logger.info("Backfilled URL for: %s @ %s", job.title, job.company)
            else:
                summary["skipped_no_match"] += 1

        session.commit()

    logger.info("Backfill complete: %s", summary)
    return summary


if __name__ == "__main__":
    setup_logging()
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    max_msgs = int(sys.argv[2]) if len(sys.argv) > 2 else 200
    print(backfill_urls(days=days, max_messages=max_msgs))
