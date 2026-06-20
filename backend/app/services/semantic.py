"""Offline resume-vs-job-description match via sentence-transformers.

Embeds the resume once (cached) and each job description, then scores by cosine
similarity (0-100). The model loads lazily on first use and is cached in-process;
the weights download once from HuggingFace and are then local.
"""
from __future__ import annotations

import os
import threading
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Session, select

from ..config import BOARD_STATUSES, STATUS_DISPLAY_MAP
from ..logging_config import logger
from ..models import Job
from .jd_fetch import fetch_job_description
from .resume_loader import resume_text

_MODEL_NAME = os.environ.get("SEMANTIC_MODEL", "all-MiniLM-L6-v2")
_MIN_JD = 200

_model = None
_resume_emb = None


def is_available() -> bool:
    try:
        import sentence_transformers  # noqa: F401

        return True
    except Exception:
        return False


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        logger.info("Loading semantic model %s (first run downloads weights)", _MODEL_NAME)
        _model = SentenceTransformer(_MODEL_NAME)
    return _model


def _resume_embedding():
    """Cached embedding of the resume text."""
    global _resume_emb
    if _resume_emb is None:
        text = resume_text()
        if not text:
            return None
        _resume_emb = _get_model().encode(text, convert_to_tensor=True)
    return _resume_emb


def semantic_score(job_description: Optional[str]) -> Optional[int]:
    """Return 0-100 cosine similarity of resume vs JD, or None if not scorable."""
    if not job_description or len(job_description) < 50:
        return None
    remb = _resume_embedding()
    if remb is None:
        return None
    try:
        from sentence_transformers import util

        jemb = _get_model().encode(job_description, convert_to_tensor=True)
        sim = float(util.cos_sim(remb, jemb))
        return max(0, min(100, round(sim * 100)))
    except Exception:
        logger.exception("Semantic scoring failed")
        return None


def has_llm_score(job: Job) -> bool:
    """True if the job already has an LLM-derived score (skip semantic then)."""
    return job.llm_match_pct is not None or job.compare_score is not None


def score_and_persist(session: Session, job: Job) -> bool:
    """Fetch the JD via the job's link if needed, compute the semantic score, and
    store it. Skips jobs that already have an LLM score. Records the attempt
    (even on failure) so un-scorable jobs aren't retried/counted forever.
    Returns True if a score was produced."""
    if has_llm_score(job) or job.semantic_score is not None:
        return False
    jd = job.job_description or ""
    if len(jd) < _MIN_JD and job.url:
        fetched = fetch_job_description(job.url)
        if fetched and len(fetched) >= _MIN_JD:
            jd = fetched
            job.job_description = fetched
    now = datetime.now(timezone.utc).isoformat()
    job.semantic_attempted_at = now
    score = semantic_score(jd)
    if score is not None:
        job.semantic_score = float(score)
        job.semantic_at = now
    session.add(job)
    return score is not None


# --- batch backfill (board jobs only; Inactive jobs are ignored) --------------

backfill_status: dict = {
    "running": False, "total": 0, "done": 0, "scored": 0, "no_jd": 0,
    "last_error": None, "last_run_iso": None,
}
_backfill_lock = threading.Lock()


def _is_active_board(job: Job) -> bool:
    if job.ignored or job.mismatched:
        return False
    disp = STATUS_DISPLAY_MAP.get(job.status or "", job.status or "Saved")
    return disp in BOARD_STATUSES


def _needs_score(job: Job) -> bool:
    """Active board job, no score yet, and not already attempted."""
    return (
        _is_active_board(job)
        and not has_llm_score(job)
        and job.semantic_score is None
        and job.semantic_attempted_at is None
        and bool(job.url)
    )


def eligible_count(session: Session) -> int:
    return sum(1 for j in session.exec(select(Job)).all() if _needs_score(j))


def run_backfill() -> None:
    """Score active-board jobs that lack any match score. Skips Inactive jobs."""
    if not _backfill_lock.acquire(blocking=False):
        logger.info("Semantic backfill already running")
        return
    from ..database import engine

    backfill_status.update(running=True, done=0, scored=0, no_jd=0, total=0, last_error=None)
    try:
        with Session(engine) as session:
            jobs = [j for j in session.exec(select(Job)).all() if _needs_score(j)]
            backfill_status["total"] = len(jobs)
            logger.info("Semantic backfill: %d board jobs to score", len(jobs))
            for job in jobs:
                if score_and_persist(session, job):
                    backfill_status["scored"] += 1
                else:
                    backfill_status["no_jd"] += 1  # attempted, no fetchable JD
                session.commit()  # persist score or the attempt marker
                backfill_status["done"] += 1
        backfill_status["last_run_iso"] = datetime.now(timezone.utc).isoformat()
    except Exception as exc:
        logger.exception("Semantic backfill failed")
        backfill_status["last_error"] = str(exc)
    finally:
        backfill_status["running"] = False
        _backfill_lock.release()
