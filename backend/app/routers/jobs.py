"""Jobs CRUD, pipeline status moves, ignore/restore, search/filter/sort,
plus per-job notes and checklist items."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlmodel import Session, select

from ..config import (
    BOARD_STATUSES,
    OFF_BOARD_STATUSES,
    PIPELINE_STATUSES,
    STATUS_DISPLAY_MAP,
)
from ..database import get_session
from ..models import ChecklistItem, Job, Note
from ..schemas import (
    BulkKeys,
    ChecklistItemIn,
    ChecklistItemOut,
    ChecklistItemUpdate,
    JobCreate,
    JobOut,
    JobUpdate,
    NoteIn,
    NoteOut,
    StatusMove,
)

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _display_status(raw: Optional[str]) -> str:
    if not raw:
        return PIPELINE_STATUSES[0]  # untracked rows surface as "Saved"
    return STATUS_DISPLAY_MAP.get(raw, raw)


def _to_out(job: Job) -> JobOut:
    return JobOut(
        job_key=job.job_key,
        title=job.title,
        company=job.company,
        location=job.location,
        url=job.url,
        salary=job.salary,
        work_mode=job.work_mode,
        source=job.source,
        status=_display_status(job.status),
        raw_status=job.status,
        match_pct=job.match_pct,
        llm_match_pct=job.llm_match_pct,
        compare_score=job.compare_score,
        compare_at=job.compare_at,
        job_description=job.job_description,
        email_date=job.email_date,
        status_updated_at=job.status_updated_at,
        ignored=bool(job.ignored),
        mismatched=bool(job.mismatched),
    )


@router.get("", response_model=List[JobOut])
def list_jobs(
    session: Session = Depends(get_session),
    q: Optional[str] = Query(None, description="search title/company/location"),
    status: Optional[str] = Query(None, description="filter by display status"),
    work_mode: Optional[str] = None,
    min_salary: Optional[int] = Query(None, description="parse salary, keep >= this"),
    include_ignored: bool = Query(False, description="show ignored jobs too"),
    only_ignored: bool = Query(False, description="show ONLY ignored jobs"),
    board_only: bool = Query(False, description="only active board statuses"),
    off_board: bool = Query(
        False, description="only off-board jobs: ignored OR Rejected/Expired"
    ),
    sort: str = Query("recent", description="recent | match | company | title"),
):
    stmt = select(Job)

    if off_board:
        pass  # need ignored + visible off-board jobs; filter in Python below
    elif only_ignored:
        stmt = stmt.where(Job.ignored == True)  # noqa: E712
    elif not include_ignored:
        stmt = stmt.where((Job.ignored == False) | (Job.ignored == None))  # noqa: E711,E712
        stmt = stmt.where((Job.mismatched == False) | (Job.mismatched == None))  # noqa: E711,E712

    if work_mode:
        stmt = stmt.where(Job.work_mode == work_mode)

    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(
            func.lower(Job.title).like(like)
            | func.lower(Job.company).like(like)
            | func.lower(Job.location).like(like)
        )

    jobs = session.exec(stmt).all()
    out = [_to_out(j) for j in jobs]

    # Off-board view: skipped, mismatched, or any off-board status.
    if off_board:
        out = [
            j for j in out
            if j.ignored or j.mismatched or j.status in OFF_BOARD_STATUSES
        ]
    # Active board: non-ignored, non-mismatched jobs in a real board column.
    if board_only:
        out = [
            j for j in out
            if not j.ignored and not j.mismatched and j.status in BOARD_STATUSES
        ]

    # Display-status filter applies after mapping (Viewed->Saved etc.).
    if status:
        out = [j for j in out if j.status == status]

    if min_salary:
        out = [j for j in out if _salary_floor(j.salary) >= min_salary]

    reverse = True
    if sort == "match":
        out.sort(key=lambda j: (j.llm_match_pct or j.match_pct or 0), reverse=True)
    elif sort == "company":
        out.sort(key=lambda j: (j.company or "").lower()); reverse = False
    elif sort == "title":
        out.sort(key=lambda j: (j.title or "").lower()); reverse = False
    else:  # recent
        out.sort(key=lambda j: (j.email_date or j.status_updated_at or ""), reverse=True)
    return out


def _salary_floor(salary: Optional[str]) -> int:
    """Best-effort lowest number found in a salary string, scaled to yearly-ish."""
    if not salary:
        return 0
    import re
    nums = [int(n.replace(",", "")) for n in re.findall(r"[\d,]{2,}", salary)]
    return min(nums) if nums else 0


@router.get("/{job_key}", response_model=JobOut)
def get_job(job_key: str, session: Session = Depends(get_session)):
    job = session.get(Job, job_key)
    if not job:
        raise HTTPException(404, "Job not found")
    return _to_out(job)


@router.post("", response_model=JobOut, status_code=201)
def create_job(payload: JobCreate, session: Session = Depends(get_session)):
    # Deterministic key from company+title+time, consistent with email-ingest style.
    seed = f"{payload.company}|{payload.title}|{_now()}"
    job_key = "manual-" + hashlib.sha1(seed.encode()).hexdigest()[:16]
    job = Job(
        job_key=job_key,
        title=payload.title,
        company=payload.company,
        location=payload.location,
        url=payload.url,
        salary=payload.salary,
        work_mode=payload.work_mode,
        job_description=payload.job_description,
        status=payload.status,
        source=payload.source or "manual",
        email_date=_now(),
        inserted_at=_now(),
        status_updated_at=_now(),
        ignored=False,
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    return _to_out(job)


@router.patch("/{job_key}", response_model=JobOut)
def update_job(job_key: str, payload: JobUpdate, session: Session = Depends(get_session)):
    job = session.get(Job, job_key)
    if not job:
        raise HTTPException(404, "Job not found")
    data = payload.model_dump(exclude_unset=True)
    if "status" in data and data["status"] is not None:
        job.status_updated_at = _now()
    for k, v in data.items():
        setattr(job, k, v)
    session.add(job)
    session.commit()
    session.refresh(job)
    return _to_out(job)


@router.patch("/{job_key}/status", response_model=JobOut)
def move_status(job_key: str, payload: StatusMove, session: Session = Depends(get_session)):
    if payload.status not in PIPELINE_STATUSES:
        raise HTTPException(400, f"status must be one of {PIPELINE_STATUSES}")
    job = session.get(Job, job_key)
    if not job:
        raise HTTPException(404, "Job not found")
    job.status = payload.status
    job.status_updated_at = _now()
    session.add(job)
    session.commit()
    session.refresh(job)
    return _to_out(job)


@router.post("/{job_key}/ignore", response_model=JobOut)
def ignore_job(job_key: str, session: Session = Depends(get_session)):
    job = session.get(Job, job_key)
    if not job:
        raise HTTPException(404, "Job not found")
    job.ignored = True
    session.add(job)
    session.commit()
    session.refresh(job)
    return _to_out(job)


@router.post("/{job_key}/restore", response_model=JobOut)
def restore_job(job_key: str, session: Session = Depends(get_session)):
    """Bring a job back to the board: clear the skipped and mismatched flags.
    Keeps the job's existing pipeline status intact."""
    job = session.get(Job, job_key)
    if not job:
        raise HTTPException(404, "Job not found")
    job.ignored = False
    job.mismatched = False
    session.add(job)
    session.commit()
    session.refresh(job)
    return _to_out(job)


def _delete_with_dependents(session: Session, job: Job) -> None:
    for note in session.exec(select(Note).where(Note.job_key == job.job_key)).all():
        session.delete(note)
    for item in session.exec(
        select(ChecklistItem).where(ChecklistItem.job_key == job.job_key)
    ).all():
        session.delete(item)
    session.delete(job)


@router.post("/bulk-restore")
def bulk_restore(payload: BulkKeys, session: Session = Depends(get_session)) -> dict:
    """Restore many jobs to the board: clear skipped/mismatched flags; move
    off-board (Rejected/Expired) ones back to Saved."""
    restored = 0
    for key in payload.job_keys:
        job = session.get(Job, key)
        if not job:
            continue
        if job.ignored or job.mismatched:
            job.ignored = False
            job.mismatched = False
        else:
            job.status = PIPELINE_STATUSES[0]  # "Saved"
            job.status_updated_at = _now()
        session.add(job)
        restored += 1
    session.commit()
    return {"restored": restored}


@router.post("/bulk-delete")
def bulk_delete(payload: BulkKeys, session: Session = Depends(get_session)) -> dict:
    deleted = 0
    for key in payload.job_keys:
        job = session.get(Job, key)
        if not job:
            continue
        _delete_with_dependents(session, job)
        deleted += 1
    session.commit()
    return {"deleted": deleted}


@router.delete("/{job_key}", status_code=204)
def delete_job(job_key: str, session: Session = Depends(get_session)):
    job = session.get(Job, job_key)
    if not job:
        raise HTTPException(404, "Job not found")
    # Clean up dependent rows first.
    for note in session.exec(select(Note).where(Note.job_key == job_key)).all():
        session.delete(note)
    for item in session.exec(
        select(ChecklistItem).where(ChecklistItem.job_key == job_key)
    ).all():
        session.delete(item)
    session.delete(job)
    session.commit()


# --- Notes --------------------------------------------------------------------

@router.get("/{job_key}/notes", response_model=List[NoteOut])
def list_notes(job_key: str, session: Session = Depends(get_session)):
    return session.exec(
        select(Note).where(Note.job_key == job_key).order_by(Note.created_at)
    ).all()


@router.post("/{job_key}/notes", response_model=NoteOut, status_code=201)
def add_note(job_key: str, payload: NoteIn, session: Session = Depends(get_session)):
    if not session.get(Job, job_key):
        raise HTTPException(404, "Job not found")
    note = Note(job_key=job_key, content=payload.content)
    session.add(note)
    session.commit()
    session.refresh(note)
    return note


@router.patch("/notes/{note_id}", response_model=NoteOut)
def update_note(note_id: int, payload: NoteIn, session: Session = Depends(get_session)):
    note = session.get(Note, note_id)
    if not note:
        raise HTTPException(404, "Note not found")
    note.content = payload.content
    note.updated_at = _now()
    session.add(note)
    session.commit()
    session.refresh(note)
    return note


@router.delete("/notes/{note_id}", status_code=204)
def delete_note(note_id: int, session: Session = Depends(get_session)):
    note = session.get(Note, note_id)
    if note:
        session.delete(note)
        session.commit()


# --- Checklist ----------------------------------------------------------------

@router.get("/{job_key}/checklist", response_model=List[ChecklistItemOut])
def list_checklist(job_key: str, session: Session = Depends(get_session)):
    return session.exec(
        select(ChecklistItem)
        .where(ChecklistItem.job_key == job_key)
        .order_by(ChecklistItem.position, ChecklistItem.id)
    ).all()


@router.post("/{job_key}/checklist", response_model=ChecklistItemOut, status_code=201)
def add_checklist_item(
    job_key: str, payload: ChecklistItemIn, session: Session = Depends(get_session)
):
    if not session.get(Job, job_key):
        raise HTTPException(404, "Job not found")
    count = session.exec(
        select(func.count()).select_from(ChecklistItem).where(
            ChecklistItem.job_key == job_key
        )
    ).one()
    item = ChecklistItem(job_key=job_key, text=payload.text, position=count)
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@router.patch("/checklist/{item_id}", response_model=ChecklistItemOut)
def update_checklist_item(
    item_id: int, payload: ChecklistItemUpdate, session: Session = Depends(get_session)
):
    item = session.get(ChecklistItem, item_id)
    if not item:
        raise HTTPException(404, "Item not found")
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(item, k, v)
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@router.delete("/checklist/{item_id}", status_code=204)
def delete_checklist_item(item_id: int, session: Session = Depends(get_session)):
    item = session.get(ChecklistItem, item_id)
    if item:
        session.delete(item)
        session.commit()
