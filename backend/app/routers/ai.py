"""AI resume-job fit endpoints.

The detailed analysis is persisted on the job (compare_analysis JSON), so it's
returned instantly on subsequent views. It only re-runs the model when the
caller passes force=true (the UI's "Re-run" button).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..config import GEMINI_MODEL, GOOGLE_API_KEY
from ..database import get_session
from ..logging_config import logger
from ..models import Job, Resume
from ..schemas import CompareRequest, CompareResult, ModelsOut
from ..services.ai import compute_fit
from ..services.gemini_client import list_models
from ..services.jd_fetch import fetch_job_description
from ..services.resume_loader import resume_text as docx_resume_text

_MIN_JD = 200  # chars below which we treat the stored description as missing

router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.get("/models", response_model=ModelsOut)
def models() -> ModelsOut:
    return ModelsOut(
        enabled=bool(GOOGLE_API_KEY), default=GEMINI_MODEL, models=list_models()
    )


def _resolve_resume(payload: CompareRequest, session: Session) -> str:
    text = payload.resume_text or ""
    if not text and payload.resume_id is not None:
        r = session.get(Resume, payload.resume_id)
        text = r.content_text if r else ""
    if not text:
        active = session.exec(
            select(Resume).where(Resume.is_active == True)  # noqa: E712
        ).first()
        text = active.content_text if active else ""
    if not text:
        # Fall back to the configured resume .docx (same one ingestion scores
        # against), so Compare works without a separately-uploaded resume.
        text = docx_resume_text()
    return text


def _saved(job: Job) -> Optional[CompareResult]:
    if not job.compare_analysis:
        return None
    try:
        return CompareResult(**json.loads(job.compare_analysis))
    except Exception:
        return None


@router.get("/compare/{job_key}", response_model=Optional[CompareResult])
def get_compare(job_key: str, session: Session = Depends(get_session)):
    """Return the saved analysis for this job, or null if none yet."""
    job = session.get(Job, job_key)
    if not job:
        raise HTTPException(404, "Job not found")
    saved = _saved(job)
    if saved:
        saved.cached = True
    return saved


@router.post("/compare/{job_key}", response_model=CompareResult)
def run_compare(
    job_key: str,
    payload: CompareRequest,
    session: Session = Depends(get_session),
):
    job = session.get(Job, job_key)
    if not job:
        raise HTTPException(404, "Job not found")

    # Return the persisted analysis unless the caller asked to re-run.
    if not payload.force:
        saved = _saved(job)
        if saved:
            saved.cached = True
            return saved

    resume_text = _resolve_resume(payload, session)
    if not resume_text:
        raise HTTPException(400, "No resume text available. Save a resume first.")

    # Ensure we have a real job description. If the stored one is missing/short,
    # try to fetch it from the posting URL and persist it on the job.
    if (not job.job_description or len(job.job_description) < _MIN_JD) and job.url:
        fetched = fetch_job_description(job.url)
        if fetched and len(fetched) >= _MIN_JD:
            job.job_description = fetched
            session.add(job)
            session.commit()

    used_jd = bool(job.job_description and len(job.job_description) >= _MIN_JD)
    header = " | ".join(filter(None, [job.title, job.company, job.location, job.salary]))
    job_text = f"{header}\n\n{job.job_description or ''}".strip()

    try:
        data = compute_fit(job_text, resume_text, model=payload.model)
    except Exception as exc:
        logger.exception("Compare failed for %s", job_key)
        # Don't persist anything on failure — the user can simply retry.
        raise HTTPException(502, f"AI analysis failed, please try again. ({exc})")

    result = CompareResult(
        job_key=job_key,
        used_job_description=used_jd,
        created_at=datetime.now(timezone.utc).isoformat(),
        cached=False,
        **data,
    )

    # Persist so it's viewable later without re-running.
    job.compare_score = float(result.match_score)
    job.compare_analysis = result.model_dump_json()
    job.compare_at = result.created_at
    session.add(job)
    session.commit()
    return result
