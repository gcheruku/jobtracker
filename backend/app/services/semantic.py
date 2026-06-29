"""Resume-vs-job-description match via embeddings (cosine similarity, 0-100).

Two backends, chosen automatically:
  * "local"  — sentence-transformers, fully offline (only in WITH_SEMANTIC
    builds; pulls in PyTorch, so it's omitted from the slim NAS image).
  * "gemini" — the Gemini embeddings API via the existing GOOGLE_API_KEY. No
    local model, no torch, negligible memory — the default in the slim build.

The resume is embedded once and cached in-process; each JD is embedded on
demand. This is the cheap, automatic score computed at ingest — distinct from
the on-demand "Compare with Resume" LLM analysis.
"""
from __future__ import annotations

import math
import os
import threading
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Session, select

from ..config import BOARD_STATUSES, GOOGLE_API_KEY, STATUS_DISPLAY_MAP
from ..logging_config import logger
from ..models import Job
from .gemini_client import _get_client
from .jd_fetch import fetch_jd_and_expiry
from .resume_loader import resume_text

_LOCAL_MODEL_NAME = os.environ.get("SEMANTIC_MODEL", "all-MiniLM-L6-v2")
_GEMINI_EMBED_MODEL = os.environ.get("SEMANTIC_GEMINI_MODEL", "gemini-embedding-001")
_MIN_JD = 200

_model = None
_resume_emb_local = None
_resume_emb_gemini: Optional[list] = None


def _local_available() -> bool:
    try:
        import sentence_transformers  # noqa: F401

        return True
    except Exception:
        return False


def backend() -> Optional[str]:
    """Which embedding backend is usable: prefer the offline local model when
    installed, else the Gemini embeddings API when a key is set, else None."""
    if _local_available():
        return "local"
    if GOOGLE_API_KEY:
        return "gemini"
    return None


def is_available() -> bool:
    return backend() is not None


def _to_pct(sim: float) -> int:
    return max(0, min(100, round(sim * 100)))


# --- local (sentence-transformers) backend ------------------------------------

def _get_model():
    global _model
    if not _local_available():
        return None
    if _model is None:
        from sentence_transformers import SentenceTransformer

        logger.info("Loading semantic model %s (first run downloads weights)", _LOCAL_MODEL_NAME)
        _model = SentenceTransformer(_LOCAL_MODEL_NAME)
    return _model


def _local_score(jd: str) -> Optional[int]:
    global _resume_emb_local
    model = _get_model()
    if model is None:
        return None
    if _resume_emb_local is None:
        text = resume_text()
        if not text:
            return None
        _resume_emb_local = model.encode(text, convert_to_tensor=True)
    try:
        from sentence_transformers import util

        jemb = model.encode(jd, convert_to_tensor=True)
        return _to_pct(float(util.cos_sim(_resume_emb_local, jemb)))
    except Exception:
        logger.exception("Local semantic scoring failed")
        return None


# --- Gemini embeddings backend (no local model / torch) -----------------------

def _gemini_embed(text: str) -> Optional[list]:
    client = _get_client()
    if client is None:
        return None
    try:
        resp = client.models.embed_content(model=_GEMINI_EMBED_MODEL, contents=[text[:20000]])
        return list(resp.embeddings[0].values)
    except Exception:
        logger.exception("Gemini embedding failed")
        return None


def _cosine(a: list, b: list) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def _gemini_score(jd: str) -> Optional[int]:
    global _resume_emb_gemini
    if _resume_emb_gemini is None:
        text = resume_text()
        if not text:
            return None
        _resume_emb_gemini = _gemini_embed(text)
        if _resume_emb_gemini is None:
            return None
    jemb = _gemini_embed(jd)
    if jemb is None:
        return None
    return _to_pct(_cosine(_resume_emb_gemini, jemb))


def semantic_score(job_description: Optional[str]) -> Optional[int]:
    """Resume↔JD similarity as 0-100, via the active backend; None if not scorable."""
    if not job_description or len(job_description) < 50:
        return None
    b = backend()
    if b == "local":
        return _local_score(job_description)
    if b == "gemini":
        return _gemini_score(job_description)
    return None


def has_llm_score(job: Job) -> bool:
    """True if the job already has an LLM-derived score (skip semantic then)."""
    return job.llm_match_pct is not None or job.compare_score is not None


def score_and_persist(session: Session, job: Job) -> str:
    """Fetch the JD via the job's link, detect expiry, and score.

    - Expired postings are moved to the "Expired" state (off the board).
    - Otherwise compute the semantic score from the JD.
    - The attempt is recorded either way so un-scorable jobs aren't retried.
    Returns "skipped" | "expired" | "scored" | "no_jd".
    """
    if has_llm_score(job) or job.semantic_score is not None:
        return "skipped"
    jd = job.job_description or ""
    expired = False
    if len(jd) < _MIN_JD and job.url:
        fetched, expired = fetch_jd_and_expiry(job.url)
        if fetched and len(fetched) >= _MIN_JD:
            jd = fetched
            job.job_description = fetched
    now = datetime.now(timezone.utc).isoformat()
    job.semantic_attempted_at = now

    if expired:
        job.status = "Expired"  # off-board; surfaces in the Inactive view
        job.status_updated_at = now
        session.add(job)
        return "expired"

    score = semantic_score(jd)
    if score is not None:
        job.semantic_score = float(score)
        job.semantic_at = now
        session.add(job)
        return "scored"
    session.add(job)
    return "no_jd"


# --- batch backfill (board jobs only; Inactive jobs are ignored) --------------

backfill_status: dict = {
    "running": False, "total": 0, "done": 0, "scored": 0, "no_jd": 0, "expired": 0,
    "last_error": None, "last_run_iso": None,
}
_backfill_lock = threading.Lock()


def _is_active_board(job: Job) -> bool:
    if job.ignored or job.mismatched:
        return False
    disp = STATUS_DISPLAY_MAP.get(job.status or "", job.status or "Saved")
    return disp in BOARD_STATUSES


def _is_saved(job: Job) -> bool:
    """On the board and still in the 'Saved' column (not yet Applied/etc.)."""
    if job.ignored or job.mismatched:
        return False
    return STATUS_DISPLAY_MAP.get(job.status or "", job.status or "Saved") == "Saved"


def _needs_score(job: Job, recheck: bool = False, saved_only: bool = False) -> bool:
    """A scorable job without a score and a URL. saved_only restricts to the
    Saved column; otherwise any active-board job qualifies. Normally also skips
    jobs already attempted; recheck=True re-processes those (e.g. for new expiry
    detection)."""
    in_scope = _is_saved(job) if saved_only else _is_active_board(job)
    return (
        in_scope
        and not has_llm_score(job)
        and job.semantic_score is None
        and bool(job.url)
        and (recheck or job.semantic_attempted_at is None)
    )


def eligible_count(session: Session, saved_only: bool = False) -> int:
    return sum(1 for j in session.exec(select(Job)).all() if _needs_score(j, saved_only=saved_only))


def run_backfill(recheck: bool = False, saved_only: bool = False) -> None:
    """Score jobs that lack any match score (skips Inactive jobs). saved_only
    restricts to the Saved column. Expired postings are moved off the board.
    recheck=True also re-processes jobs already attempted."""
    if not _backfill_lock.acquire(blocking=False):
        logger.info("Semantic backfill already running")
        return
    from ..database import engine

    backfill_status.update(
        running=True, done=0, scored=0, no_jd=0, expired=0, total=0, last_error=None,
        scope="saved" if saved_only else "board",
    )
    try:
        with Session(engine) as session:
            jobs = [
                j for j in session.exec(select(Job)).all()
                if _needs_score(j, recheck, saved_only)
            ]
            backfill_status["total"] = len(jobs)
            logger.info("Semantic backfill: %d jobs (recheck=%s)", len(jobs), recheck)
            for job in jobs:
                result = score_and_persist(session, job)
                if result == "scored":
                    backfill_status["scored"] += 1
                elif result == "expired":
                    backfill_status["expired"] += 1
                else:
                    backfill_status["no_jd"] += 1
                session.commit()  # persist score / status / attempt marker
                backfill_status["done"] += 1
        backfill_status["last_run_iso"] = datetime.now(timezone.utc).isoformat()
    except Exception as exc:
        logger.exception("Semantic backfill failed")
        backfill_status["last_error"] = str(exc)
    finally:
        backfill_status["running"] = False
        _backfill_lock.release()
