"""AI resume-job fit endpoint. Resolves the resume + job text, then delegates to
the AI service (LLM if configured, heuristic stub otherwise)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..database import get_session
from ..models import Job, Resume
from ..schemas import CompareRequest, CompareResult
from ..services.ai import compare_resume_to_job

router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.post("/compare/{job_key}", response_model=CompareResult)
def compare(
    job_key: str,
    payload: CompareRequest,
    session: Session = Depends(get_session),
):
    job = session.get(Job, job_key)
    if not job:
        raise HTTPException(404, "Job not found")

    # Resolve resume text: inline > referenced id > active resume.
    resume_text = payload.resume_text or ""
    if not resume_text and payload.resume_id is not None:
        resume = session.get(Resume, payload.resume_id)
        resume_text = resume.content_text if resume else ""
    if not resume_text:
        active = session.exec(
            select(Resume).where(Resume.is_active == True)  # noqa: E712
        ).first()
        resume_text = active.content_text if active else ""

    if not resume_text:
        raise HTTPException(
            400, "No resume text available. Upload/paste a resume first."
        )

    job_text = "\n".join(
        filter(None, [job.title, job.company, job.location, job.job_description])
    )
    return compare_resume_to_job(job_key, job_text, resume_text)
