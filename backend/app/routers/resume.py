"""Resume management: paste text or upload a PDF/txt. Stored in the resume table.

PDF text extraction uses pypdf when available; otherwise the raw upload is stored
and the user can paste text manually. The extracted/pasted `content_text` is what
the AI compare endpoint consumes.
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlmodel import Session, select

from ..config import RESUME_UPLOAD_DIR
from ..database import get_session
from ..models import Resume
from ..schemas import ResumeOut, ResumeTextIn

router = APIRouter(prefix="/api/resumes", tags=["resumes"])


def _deactivate_others(session: Session, keep_id: Optional[int]) -> None:
    for r in session.exec(select(Resume).where(Resume.is_active == True)).all():  # noqa: E712
        if r.id != keep_id:
            r.is_active = False
            session.add(r)


@router.get("", response_model=List[ResumeOut])
def list_resumes(session: Session = Depends(get_session)):
    return session.exec(select(Resume).order_by(Resume.uploaded_at.desc())).all()


@router.get("/active", response_model=Optional[ResumeOut])
def active_resume(session: Session = Depends(get_session)):
    return session.exec(
        select(Resume).where(Resume.is_active == True)  # noqa: E712
    ).first()


@router.post("/text", response_model=ResumeOut, status_code=201)
def save_resume_text(payload: ResumeTextIn, session: Session = Depends(get_session)):
    resume = Resume(
        name=payload.name or "My Resume",
        content_text=payload.content_text,
        mime_type="text/plain",
        is_active=True,
    )
    session.add(resume)
    session.flush()
    _deactivate_others(session, resume.id)
    session.commit()
    session.refresh(resume)
    return resume


@router.post("/upload", response_model=ResumeOut, status_code=201)
async def upload_resume(
    file: UploadFile = File(...),
    name: str = Form("My Resume"),
    session: Session = Depends(get_session),
):
    RESUME_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    raw = await file.read()
    stored_path = RESUME_UPLOAD_DIR / file.filename
    stored_path.write_bytes(raw)

    content_text = ""
    if (file.content_type or "").startswith("text") or file.filename.endswith(".txt"):
        content_text = raw.decode("utf-8", errors="ignore")
    elif file.filename.lower().endswith(".pdf"):
        try:
            from pypdf import PdfReader
            import io

            reader = PdfReader(io.BytesIO(raw))
            content_text = "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception:
            content_text = ""  # user can paste text via /text if extraction fails

    resume = Resume(
        name=name,
        content_text=content_text,
        file_name=file.filename,
        stored_path=str(stored_path),
        mime_type=file.content_type,
        is_active=True,
    )
    session.add(resume)
    session.flush()
    _deactivate_others(session, resume.id)
    session.commit()
    session.refresh(resume)
    return resume


@router.post("/{resume_id}/activate", response_model=ResumeOut)
def activate_resume(resume_id: int, session: Session = Depends(get_session)):
    resume = session.get(Resume, resume_id)
    if not resume:
        raise HTTPException(404, "Resume not found")
    resume.is_active = True
    session.add(resume)
    _deactivate_others(session, resume.id)
    session.commit()
    session.refresh(resume)
    return resume


@router.delete("/{resume_id}", status_code=204)
def delete_resume(resume_id: int, session: Session = Depends(get_session)):
    resume = session.get(Resume, resume_id)
    if resume:
        session.delete(resume)
        session.commit()
