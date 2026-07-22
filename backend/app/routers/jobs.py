"""Jobs CRUD, pipeline status moves, ignore/restore, search/filter/sort,
plus per-job notes and checklist items."""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlmodel import Session, select

from ..config import (
    BOARD_STATUSES,
    OFF_BOARD_STATUSES,
    PIPELINE_STATUSES,
    STATUS_DISPLAY_MAP,
)
from ..database import get_session
from ..logging_config import logger
from ..models import ChecklistItem, CompanyPortal, Job, Note
from ..services.gemini_client import extract_job_fields
from ..services.jd_fetch import fetch_job_description, fetch_job_posting
from ..services.semantic import score_and_persist
from ..schemas import (
    BulkKeys,
    BulkStatus,
    BulkWatchlist,
    ChecklistItemIn,
    ChecklistItemOut,
    ChecklistItemUpdate,
    JobCreate,
    JobFromURL,
    JobOut,
    JobUpdate,
    NoteIn,
    NoteOut,
    PortalIn,
    StatusMove,
    WatchlistToggle,
)

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


# Board columns you're actively working, as opposed to the "Saved" candidate
# pool. Used by the search "hide in-pipeline" toggle.
ACTIVE_PIPELINE_STATUSES = [s for s in BOARD_STATUSES if s != BOARD_STATUSES[0]]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _display_status(raw: Optional[str]) -> str:
    if not raw:
        return PIPELINE_STATUSES[0]  # untracked rows surface as "Saved"
    return STATUS_DISPLAY_MAP.get(raw, raw)


def _company_key(company: Optional[str]) -> str:
    """Normalize a company name into the lookup key for its shared portal URL:
    lowercased with collapsed internal whitespace, so trivial variations of the
    same company still map to one entry."""
    return re.sub(r"\s+", " ", (company or "").strip()).lower()


def _portal_url(session: Session, company: Optional[str]) -> Optional[str]:
    key = _company_key(company)
    if not key:
        return None
    row = session.get(CompanyPortal, key)
    return row.portal_url if row and row.portal_url else None


def _to_out(job: Job, portal_url: Optional[str] = None) -> JobOut:
    return JobOut(
        job_key=job.job_key,
        title=job.title,
        company=job.company,
        location=job.location,
        url=job.url,
        salary=job.salary,
        work_mode=job.work_mode,
        distance_miles=job.distance_miles,
        source=job.source,
        status=_display_status(job.status),
        raw_status=job.status,
        match_pct=job.match_pct,
        llm_match_pct=job.llm_match_pct,
        semantic_score=job.semantic_score,
        compare_score=job.compare_score,
        compare_at=job.compare_at,
        job_description=job.job_description,
        email_date=job.email_date,
        status_updated_at=job.status_updated_at,
        ignored=bool(job.ignored),
        mismatched=bool(job.mismatched),
        mismatch_reason=job.mismatch_reason,
        watchlist=bool(job.watchlist),
        portal_url=portal_url,
    )


def _out(session: Session, job: Job) -> JobOut:
    """_to_out with the company's shared portal URL looked up (single-job paths)."""
    return _to_out(job, _portal_url(session, job.company))


def _phrase_pattern(q: str) -> Optional[re.Pattern[str]]:
    """Compile a whole-word, contiguous-phrase matcher for the "phrase" search
    mode. 'software engineer' matches 'Senior Software Engineer' but NOT
    'Software Engineering Manager' (the trailing \\b stops 'engineer' from
    matching inside 'engineering'). Tolerates irregular spacing between words."""
    tokens = [re.escape(t) for t in q.lower().split()]
    if not tokens:
        return None
    return re.compile(r"\b" + r"\s+".join(tokens) + r"\b")


@router.get("", response_model=List[JobOut])
def list_jobs(
    session: Session = Depends(get_session),
    q: Optional[str] = Query(None, description="search title/company/location"),
    match: str = Query(
        "all", description="search mode: 'all' words, 'any' word, or exact 'phrase'"
    ),
    status: Optional[str] = Query(None, description="filter by display status"),
    work_mode: Optional[str] = None,
    min_salary: Optional[int] = Query(None, description="parse salary, keep >= this"),
    include_ignored: bool = Query(False, description="show ignored jobs too"),
    only_ignored: bool = Query(False, description="show ONLY ignored jobs"),
    board_only: bool = Query(False, description="only active board statuses"),
    off_board: bool = Query(
        False, description="only off-board jobs: ignored OR Rejected/Expired"
    ),
    only_mismatched: bool = Query(False, description="only preference-mismatched jobs"),
    watchlist: bool = Query(False, description="only watchlisted (starred) jobs"),
    hide_watchlist: bool = Query(False, description="drop watchlisted (starred) jobs"),
    hide_pipeline: bool = Query(
        False, description="drop jobs already in the pipeline (Applied/Interviewing/Offer)"
    ),
    sort: str = Query("recent", description="recent | match | semantic | company | title"),
):
    stmt = select(Job)

    if off_board or only_mismatched:
        pass  # fetch all; filter precisely in Python below
    elif only_ignored:
        stmt = stmt.where(Job.ignored == True)  # noqa: E712
    elif not include_ignored:
        stmt = stmt.where((Job.ignored == False) | (Job.ignored == None))  # noqa: E711,E712
        stmt = stmt.where((Job.mismatched == False) | (Job.mismatched == None))  # noqa: E711,E712

    if work_mode:
        stmt = stmt.where(Job.work_mode == work_mode)

    if q and match != "phrase":
        tokens = q.lower().split()
        # A word matches if it's a substring of SOME column (title/company/
        # location); words need not be contiguous or in the same column.
        per_word = [
            func.lower(Job.title).like(f"%{t}%")
            | func.lower(Job.company).like(f"%{t}%")
            | func.lower(Job.location).like(f"%{t}%")
            for t in tokens
        ]
        if match == "any":
            # "any": at least one word matches. e.g. "remote staff" -> either.
            if per_word:
                stmt = stmt.where(or_(*per_word))
        else:
            # "all" (default): every word must match somewhere.
            for clause in per_word:
                stmt = stmt.where(clause)

    jobs = session.exec(stmt).all()
    # Batch-load every company's shared portal URL once, then map by company —
    # avoids an N+1 query per job in the list.
    portals = {
        p.company_key: p.portal_url
        for p in session.exec(select(CompanyPortal)).all()
        if p.portal_url
    }
    out = [_to_out(j, portals.get(_company_key(j.company))) for j in jobs]

    # "phrase": exact, whole-word contiguous match, refined in Python so
    # "software engineer" excludes "Software Engineering Manager".
    if q and match == "phrase":
        pat = _phrase_pattern(q)
        if pat is not None:
            out = [
                j for j in out
                if pat.search((j.title or "").lower())
                or pat.search((j.company or "").lower())
                or pat.search((j.location or "").lower())
            ]

    # Mismatched view: preference-mismatched jobs only.
    if only_mismatched:
        out = [j for j in out if j.mismatched]
    # Off-board (Inactive) view: skipped or off-board status, EXCLUDING
    # mismatched (those have their own view).
    if off_board:
        out = [
            j for j in out
            if not j.mismatched and (j.ignored or j.status in OFF_BOARD_STATUSES)
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

    if watchlist:
        out = [j for j in out if j.watchlist]
    if hide_watchlist:
        out = [j for j in out if not j.watchlist]

    # "Hide in-pipeline": keep only the Saved candidate pool, dropping jobs
    # you're already working (Applied/Interviewing/Offer).
    if hide_pipeline:
        out = [j for j in out if j.status not in ACTIVE_PIPELINE_STATUSES]

    reverse = True
    if sort == "match":
        out.sort(key=lambda j: (j.llm_match_pct or j.match_pct or 0), reverse=True)
    elif sort == "semantic":
        out.sort(key=lambda j: (j.semantic_score or 0), reverse=True)
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
    nums = [int(n.replace(",", "")) for n in re.findall(r"[\d,]{2,}", salary)]
    return min(nums) if nums else 0


@router.get("/{job_key}", response_model=JobOut)
def get_job(job_key: str, session: Session = Depends(get_session)):
    job = session.get(Job, job_key)
    if not job:
        raise HTTPException(404, "Job not found")
    return _out(session, job)


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
    return _out(session, job)


@router.post("/from-url", response_model=JobOut, status_code=201)
def create_job_from_url(payload: JobFromURL, session: Session = Depends(get_session)):
    """Add a job from a career-portal posting URL: fetch the page, read its
    title/company/location/salary + description (JSON-LD, with an LLM fallback),
    create the job, and run the semantic match. LLM compare is run on demand from
    the UI afterwards (the description is now stored, so it works)."""
    url = (payload.url or "").strip()
    if not url.lower().startswith(("http://", "https://")):
        raise HTTPException(400, "Provide a valid job posting URL (http/https).")

    # Idempotent: if this exact posting is already tracked, just return it.
    existing = session.exec(select(Job).where(Job.url == url)).first()
    if existing:
        return _out(session, existing)

    posting = fetch_job_posting(url)
    if posting.not_found:
        raise HTTPException(422, "That posting page returned 404 — check the link.")

    title, company = posting.title, posting.company
    location, salary, work_mode = posting.location, posting.salary, ""
    # Fill anything the structured data missed via the LLM (best-effort).
    if (not title or not company) and posting.description:
        fields = extract_job_fields(posting.description, url)
        title = title or fields.get("title", "")
        company = company or fields.get("company", "")
        location = location or fields.get("location", "")
        salary = salary or fields.get("salary", "")
        work_mode = fields.get("work_mode", "")

    if not title and not company:
        raise HTTPException(
            422,
            "Couldn't read the job details from that link (it may require login or "
            "block automated access). Try the company's direct posting URL, or add "
            "it manually with the fields you have.",
        )

    seed = f"{company}|{title}|{_now()}"
    job = Job(
        job_key="manual-" + hashlib.sha1(seed.encode()).hexdigest()[:16],
        title=title or None,
        company=company or None,
        location=location or None,
        url=url,
        salary=salary or None,
        work_mode=work_mode or None,
        job_description=posting.description or None,
        source="Manual",
        # NOTE: deliberately no email_epoch — that column feeds the Gmail ingest
        # watermark, and a manual add must never advance it.
        email_date=_now(),
        inserted_at=_now(),
        status=PIPELINE_STATUSES[0],  # "Saved"
        status_updated_at=_now(),
        ignored=False,
    )
    session.add(job)
    session.commit()
    session.refresh(job)

    # Semantic match now (JD already stored; score_and_persist uses it directly).
    try:
        score_and_persist(session, job)
        session.commit()
        session.refresh(job)
    except Exception:
        logger.exception("Semantic scoring failed for %s", job.job_key)

    return _out(session, job)


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
    return _out(session, job)


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
    return _out(session, job)


@router.post("/{job_key}/ignore", response_model=JobOut)
def ignore_job(job_key: str, session: Session = Depends(get_session)):
    job = session.get(Job, job_key)
    if not job:
        raise HTTPException(404, "Job not found")
    job.ignored = True
    session.add(job)
    session.commit()
    session.refresh(job)
    return _out(session, job)


@router.put("/{job_key}/portal", response_model=JobOut)
def set_company_portal(
    job_key: str, payload: PortalIn, session: Session = Depends(get_session)
):
    """Set the candidate-portal home page for this job's company. The URL is
    stored per-company, so every job at the same company shares it."""
    job = session.get(Job, job_key)
    if not job:
        raise HTTPException(404, "Job not found")
    key = _company_key(job.company)
    if not key:
        raise HTTPException(400, "Job has no company to attach a portal URL to")
    url = (payload.portal_url or "").strip()
    if not url.lower().startswith(("http://", "https://")):
        raise HTTPException(400, "Provide a valid portal URL (http/https).")

    row = session.get(CompanyPortal, key)
    if row:
        row.portal_url = url
        row.company = job.company or row.company
        row.updated_at = _now()
    else:
        row = CompanyPortal(company_key=key, company=job.company or "", portal_url=url)
    session.add(row)
    session.commit()
    return _out(session, job)


@router.delete("/{job_key}/portal", response_model=JobOut)
def clear_company_portal(job_key: str, session: Session = Depends(get_session)):
    """Remove the shared candidate-portal URL for this job's company."""
    job = session.get(Job, job_key)
    if not job:
        raise HTTPException(404, "Job not found")
    row = session.get(CompanyPortal, _company_key(job.company))
    if row:
        session.delete(row)
        session.commit()
    return _out(session, job)


@router.post("/{job_key}/watchlist", response_model=JobOut)
def set_watchlist(
    job_key: str, payload: WatchlistToggle, session: Session = Depends(get_session)
):
    """Star/unstar a job for later revisit (orthogonal to pipeline status)."""
    job = session.get(Job, job_key)
    if not job:
        raise HTTPException(404, "Job not found")
    job.watchlist = payload.on
    session.add(job)
    session.commit()
    session.refresh(job)
    return _out(session, job)


@router.post("/bulk-watchlist")
def bulk_watchlist(payload: BulkWatchlist, session: Session = Depends(get_session)) -> dict:
    """Star/unstar many jobs in one transaction."""
    updated = 0
    for key in payload.job_keys:
        job = session.get(Job, key)
        if not job:
            continue
        job.watchlist = payload.on
        session.add(job)
        updated += 1
    session.commit()
    return {"updated": updated, "on": payload.on}


@router.post("/{job_key}/refresh-description", response_model=JobOut)
def refresh_description(job_key: str, session: Session = Depends(get_session)):
    """Re-fetch the job description from the posting (stored as Markdown)."""
    job = session.get(Job, job_key)
    if not job:
        raise HTTPException(404, "Job not found")
    if not job.url:
        raise HTTPException(400, "Job has no URL to fetch a description from")
    desc = fetch_job_description(job.url)
    if desc:
        job.job_description = desc
        session.add(job)
        session.commit()
        session.refresh(job)
    return _out(session, job)


@router.post("/{job_key}/restore", response_model=JobOut)
def restore_job(job_key: str, session: Session = Depends(get_session)):
    """Bring a job back to the board: clear the skipped and mismatched flags.
    Keeps the job's existing pipeline status intact."""
    job = session.get(Job, job_key)
    if not job:
        raise HTTPException(404, "Job not found")
    job.ignored = False
    job.mismatched = False
    job.mismatch_reason = None
    session.add(job)
    session.commit()
    session.refresh(job)
    return _out(session, job)


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
            job.mismatch_reason = None
        else:
            job.status = PIPELINE_STATUSES[0]  # "Saved"
            job.status_updated_at = _now()
        session.add(job)
        restored += 1
    session.commit()
    return {"restored": restored}


@router.post("/bulk-ignore")
def bulk_ignore(payload: BulkKeys, session: Session = Depends(get_session)) -> dict:
    """Skip (ignore) many jobs in a single transaction. Doing this in one request
    avoids the SQLite write contention and partial failures that firing one
    request per job caused for large selections."""
    ignored = 0
    for key in payload.job_keys:
        job = session.get(Job, key)
        if not job:
            continue
        if not job.ignored:
            job.ignored = True
            session.add(job)
        ignored += 1
    session.commit()
    return {"ignored": ignored}


@router.post("/bulk-status")
def bulk_status(payload: BulkStatus, session: Session = Depends(get_session)) -> dict:
    """Move many jobs to a pipeline status in a single transaction."""
    if payload.status not in PIPELINE_STATUSES:
        raise HTTPException(400, f"status must be one of {PIPELINE_STATUSES}")
    updated = 0
    for key in payload.job_keys:
        job = session.get(Job, key)
        if not job:
            continue
        job.status = payload.status
        job.status_updated_at = _now()
        session.add(job)
        updated += 1
    session.commit()
    return {"updated": updated}


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
