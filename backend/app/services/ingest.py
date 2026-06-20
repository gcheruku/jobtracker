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

import hashlib
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
from .email_parser import build_payload, is_job_email
from .gemini_client import extract_jobs, score_job
from .resume_loader import resume_text

_lock = threading.Lock()

status: dict = {
    "running": False,
    "last_run_iso": None,
    "last_summary": None,
    "last_error": None,
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm(s: str | None) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def _job_key(provider: str, job: dict) -> str:
    """Stable identity for dedup. Prefer URL; fall back to title|company."""
    url = (job.get("url") or "").strip()
    if url:
        return f"{provider}:url:" + hashlib.sha1(url.encode()).hexdigest()[:16]
    return f"{provider}:{_norm(job.get('title'))}|{_norm(job.get('company'))}"


def _watermark(session: Session) -> int:
    db_max = session.exec(select(Job.email_epoch)).all()
    db_max = max([e for e in db_max if e] or [0])
    meta = session.exec(
        text("SELECT value FROM meta WHERE key='last_run_epoch'")
    ).first()
    meta_val = int(meta[0]) if meta and str(meta[0]).isdigit() else 0
    return max(db_max, meta_val)


def _existing_urls(session: Session) -> set[str]:
    rows = session.exec(text("SELECT url FROM jobs WHERE url IS NOT NULL")).all()
    return {r[0] for r in rows if r[0]}


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


def run_ingest(max_messages: int = INGEST_MAX_MESSAGES) -> dict:
    """Synchronous ingest. Returns a summary dict; also stored in `status`."""
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
            watermark = _watermark(session)
            seen_urls = _existing_urls(session)
            seen_keys: set[str] = set()
            resume = resume_text()
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

                for job in extract_jobs(payload):
                    if not job.get("title") or not job.get("company"):
                        continue
                    summary["jobs_found"] += 1
                    key = _job_key(payload.provider, job)
                    url = (job.get("url") or "").strip()
                    if key in seen_keys or (url and url in seen_urls):
                        summary["duplicates"] += 1
                        continue
                    if session.get(Job, key):
                        summary["duplicates"] += 1
                        continue
                    seen_keys.add(key)
                    if url:
                        seen_urls.add(url)

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

                    scored = score_job(job, resume)
                    if scored:
                        row.llm_match_pct = float(scored.get("match", 0))
                        row.match_pct = row.llm_match_pct
                        row.llm_analysis = (scored.get("summary") or "")[:1000]
                        row.llm_analysis_at = _now_iso()
                        row.match_scored_at = _now_iso()
                        summary["scored"] += 1

                    session.add(row)
                    summary["new_jobs"] += 1

                session.commit()  # commit per-email so partial runs persist

            _save_watermark(session, newest_epoch)

        summary["watermark_advanced_to"] = datetime.fromtimestamp(
            newest_epoch, tz=timezone.utc
        ).isoformat()
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
