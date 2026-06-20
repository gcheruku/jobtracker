"""SQLModel table definitions.

`Job` is mapped onto the EXISTING `jobs` table (1,571 rows). We keep every
original column and only ADD nullable columns (`ignored`, `work_mode`) via a
non-destructive startup migration in database.py.

`Note`, `Resume`, and `ChecklistItem` are brand-new tables created by
SQLModel.metadata.create_all — they sit alongside the existing data.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Job(SQLModel, table=True):
    # Bind to the pre-existing table rather than creating a new one.
    __tablename__ = "jobs"

    job_key: str = Field(primary_key=True)
    title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    source: Optional[str] = None
    url: Optional[str] = None
    email_date: Optional[str] = None
    email_epoch: Optional[int] = None
    message_id: Optional[str] = None
    inserted_at: Optional[str] = None

    # Scoring / analysis columns already present in jobs.db.
    match_pct: Optional[float] = None
    match_scored_at: Optional[str] = None
    job_description: Optional[str] = None
    status: Optional[str] = None
    status_updated_at: Optional[str] = None
    llm_analysis: Optional[str] = None
    llm_analysis_at: Optional[str] = None
    llm_match_pct: Optional[float] = None
    salary: Optional[str] = None

    # --- Columns ADDED by this app (created by the startup migration) ---
    # Hidden from the default view but retained in the DB; restorable/deletable.
    ignored: Optional[bool] = Field(default=False)
    # Remote / Hybrid / On-site — powers the Work Mode filter.
    work_mode: Optional[str] = None
    # Detailed "Compare with Resume" analysis (persisted so it's viewable later).
    compare_score: Optional[float] = None
    compare_analysis: Optional[str] = None  # full CompareResult JSON
    compare_at: Optional[str] = None


class Note(SQLModel, table=True):
    __tablename__ = "note"

    id: Optional[int] = Field(default=None, primary_key=True)
    job_key: str = Field(index=True, foreign_key="jobs.job_key")
    content: str = ""
    created_at: str = Field(default_factory=utcnow_iso)
    updated_at: str = Field(default_factory=utcnow_iso)


class ChecklistItem(SQLModel, table=True):
    __tablename__ = "checklist_item"

    id: Optional[int] = Field(default=None, primary_key=True)
    job_key: str = Field(index=True, foreign_key="jobs.job_key")
    text: str
    done: bool = False
    position: int = 0
    created_at: str = Field(default_factory=utcnow_iso)


class Resume(SQLModel, table=True):
    __tablename__ = "resume"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = "My Resume"
    content_text: str = ""           # extracted/pasted plain text used for AI compare
    file_name: Optional[str] = None  # original upload filename, if any
    stored_path: Optional[str] = None
    mime_type: Optional[str] = None
    is_active: bool = True           # the resume used by default for comparisons
    uploaded_at: str = Field(default_factory=utcnow_iso)
