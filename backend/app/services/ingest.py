"""Ingestion orchestrator.

Flow (requirements 2-5 of the prompt):
  1. Watermark = latest discovered job in the DB (max jobs.email_epoch),
     falling back to meta.last_run_epoch.
  2. Fetch Job-alert emails delivered after the watermark.
  3. Extract jobs (Gemini), score each against the resume (Gemini).
  4. Dedup by job URL, else by a stable source:title|company key — some alerts
     are resent, so we skip jobs already in the DB.
  5. Save the new latest fetch timestamp into the meta table.

A module-level lock + status dict make runs safe to trigger from both the
scheduler and the manual endpoint, and let the UI poll progress.
"""
from __future__ import annotations

import re
import threading
from datetime import datetime, timezone

from sqlalchemy import text
from sqlmodel import Session, select

from ..config import GMAIL_LABEL, INGEST_MAX_MESSAGES
from ..database import engine
from ..logging_config import logger
from ..models import Job
from . import gmail_client as gm
from .alert_parsers import parse_glassdoor, parse_indeed
from .email_parser import build_payload, is_job_email, norm
from .gemini_client import parse_tiles
from .semantic import score_and_persist

_lock = threading.Lock()

status: dict = {
    "running": False,
    "last_run_iso": None,
    "last_summary": None,
    "last_error": None,
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe(s: str) -> str:
    # Slashes break FastAPI path-param routing even when URL-encoded, so keep
    # them (and backslashes) out of the job_key, which is used in URL paths.
    return s.replace("/", "-").replace("\\", "-")


def canonical_id(url: str | None) -> str | None:
    """The stable posting id embedded in a job URL (tracking params vary per
    email, so we key on the id, not the full URL). None if no id is present."""
    if not url:
        return None
    low = url.lower()
    if "linkedin" in low:
        m = re.search(r"/jobs/view/(\d+)", low) or re.search(r"currentjobid=(\d+)", low)
        return f"li-{m.group(1)}" if m else None
    if "indeed" in low:
        m = re.search(r"[?&]jk=([0-9a-z]+)", low)
        return f"in-{m.group(1)}" if m else None
    if "glassdoor" in low:
        m = re.search(r"[?&]joblistingid=(\d+)", low)
        return f"gd-{m.group(1)}" if m else None
    return None


def _job_key(provider: str, job: dict) -> str:
    """Stable identity key. Prefer the posting id from the URL so DISTINCT
    postings of the same title/company are kept separate; fall back to
    title|company only when no posting id is available."""
    cid = canonical_id(job.get("url"))
    if cid:
        return f"{provider}:{cid}"
    return f"{provider}:{_safe(norm(job.get('title')))}|{_safe(norm(job.get('company')))}"


def _watermark(session: Session) -> int:
    db_max = session.exec(select(Job.email_epoch)).all()
    db_max = max([e for e in db_max if e] or [0])
    meta = session.exec(
        text("SELECT value FROM meta WHERE key='last_run_epoch'")
    ).first()
    meta_val = int(meta[0]) if meta and str(meta[0]).isdigit() else 0
    return max(db_max, meta_val)


def _existing_ids(session: Session) -> set[str]:
    """Canonical posting ids of every job already in the DB (from their URLs).
    Dedup keys on this so DISTINCT postings of the same role are all kept."""
    rows = session.exec(text("SELECT url FROM jobs WHERE url IS NOT NULL")).all()
    return {cid for r in rows if r[0] and (cid := canonical_id(r[0]))}


def _existing_pairs(session: Session) -> set[tuple[str, str]]:
    """(title, company) of jobs WITHOUT a canonical posting id — the fallback
    dedup for postings whose link carries no id."""
    rows = session.exec(text("SELECT title, company, url FROM jobs")).all()
    return {
        (norm(r[0]), norm(r[1]))
        for r in rows
        if r[0] and r[1] and not canonical_id(r[2])
    }


def _save_watermark(session: Session, epoch: int) -> None:
    iso = datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()
    for key, val in (("last_run_epoch", str(epoch)), ("last_fetch_iso", iso)):
        session.exec(
            text(
                "INSERT INTO meta(key,value) VALUES(:k,:v) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value"
            ).bindparams(k=key, v=val)
        )
    session.commit()


def run_ingest(
    max_messages: int = INGEST_MAX_MESSAGES, since_epoch: int | None = None
) -> dict:
    """Synchronous ingest. Returns a summary dict; also stored in `status`.

    since_epoch overrides the watermark to reprocess older emails (e.g. after a
    dedup fix); dedup still prevents re-adding jobs already in the DB.
    """
    if not _lock.acquire(blocking=False):
        logger.info("Ingest already running; skipping this trigger")
        return {"skipped": "already running"}

    status.update(running=True, last_error=None)
    summary = {
        "emails_scanned": 0, "jobs_found": 0, "new_jobs": 0,
        "duplicates": 0, "scored": 0,
    }
    try:
        service = gm.get_service()
        label_id = gm.get_label_id(service, GMAIL_LABEL)
        if not label_id:
            raise RuntimeError(f"Gmail label '{GMAIL_LABEL}' not found")

        with Session(engine) as session:
            watermark = since_epoch if since_epoch is not None else _watermark(session)
            seen_ids = _existing_ids(session)
            seen_pairs = _existing_pairs(session)
            newest_epoch = watermark

            msg_ids = gm.list_message_ids(service, label_id, watermark, max_messages)
            logger.info(
                "Ingest: %d candidate emails after %s",
                len(msg_ids),
                datetime.fromtimestamp(watermark, tz=timezone.utc).isoformat()
                if watermark else "(beginning)",
            )

            for msg_id in msg_ids:
                full = gm.fetch_message(service, msg_id)
                if gm.internal_epoch(full) <= watermark:
                    continue  # day-granular query over-fetches; enforce precisely
                payload = build_payload(full)
                if not is_job_email(payload.subject):
                    continue
                summary["emails_scanned"] += 1
                newest_epoch = max(newest_epoch, payload.epoch)

                # Deterministic parsers for Indeed (plain text) and Glassdoor
                # (HTML); LinkedIn/other fall back to the LLM tile extractor.
                if payload.provider == "Indeed":
                    jobs = parse_indeed(gm.plain_text_body(full["payload"]))
                elif payload.provider == "Glassdoor":
                    jobs = parse_glassdoor(gm.html_body(full["payload"]))
                else:
                    jobs = parse_tiles(payload.links)

                for job in jobs:
                    if not job.get("title") or not job.get("company"):
                        continue
                    summary["jobs_found"] += 1
                    url = (job.get("url") or "").strip()
                    key = _job_key(payload.provider, job)
                    cid = canonical_id(url)
                    # Dedup by the posting id from the link (distinct postings of
                    # the same role are kept). Fall back to title|company only
                    # when the link carries no id.
                    if cid:
                        if cid in seen_ids:
                            summary["duplicates"] += 1
                            continue
                        seen_ids.add(cid)
                    else:
                        pair = (norm(job.get("title")), norm(job.get("company")))
                        if pair in seen_pairs:
                            summary["duplicates"] += 1
                            continue
                        seen_pairs.add(pair)

                    row = Job(
                        job_key=key,
                        title=job.get("title"),
                        company=job.get("company"),
                        location=job.get("location") or None,
                        url=url or None,
                        salary=job.get("salary") or None,
                        source=payload.provider,
                        email_date=datetime.fromtimestamp(
                            payload.epoch, tz=timezone.utc
                        ).isoformat(),
                        email_epoch=payload.epoch,
                        message_id=payload.message_id,
                        inserted_at=_now_iso(),
                        status=None,  # untracked -> surfaces under "Saved"
                        ignored=False,
                    )

                    session.add(row)
                    summary["new_jobs"] += 1
                    # Offline semantic match: pull the JD via the link and score
                    # resume vs JD (skips jobs that already have an LLM score).
                    status["phase"] = "scoring"
                    if score_and_persist(session, row) == "scored":
                        summary["scored"] += 1
                    status["scored_so_far"] = summary["scored"]

                session.commit()  # commit per-email so partial runs persist

            _save_watermark(session, newest_epoch)

        summary["watermark_advanced_to"] = datetime.fromtimestamp(
            newest_epoch, tz=timezone.utc
        ).isoformat()

        # Fill distance_miles for the jobs we just added (cached geocoding).
        try:
            from .distance import backfill_distances

            backfill_distances()
        except Exception:
            logger.exception("Distance backfill after ingest failed")

        status.update(last_summary=summary, last_run_iso=_now_iso())
        logger.info("Ingest complete: %s", summary)
        return summary
    except Exception as exc:
        logger.exception("Ingest failed")
        status.update(last_error=str(exc), last_run_iso=_now_iso())
        return {"error": str(exc)}
    finally:
        status.update(running=False)
        _lock.release()
