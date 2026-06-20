"""Pydantic request/response models for the API surface."""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel

from .config import PIPELINE_STATUSES


class JobCreate(BaseModel):
    title: str
    company: str
    location: Optional[str] = None
    url: Optional[str] = None
    salary: Optional[str] = None
    work_mode: Optional[str] = None          # Remote / Hybrid / On-site
    job_description: Optional[str] = None
    status: str = PIPELINE_STATUSES[0]        # defaults to "Saved"
    source: Optional[str] = "manual"


class JobUpdate(BaseModel):
    title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    url: Optional[str] = None
    salary: Optional[str] = None
    work_mode: Optional[str] = None
    job_description: Optional[str] = None
    status: Optional[str] = None


class StatusMove(BaseModel):
    status: str


class BulkKeys(BaseModel):
    job_keys: List[str]


class JobOut(BaseModel):
    job_key: str
    title: Optional[str]
    company: Optional[str]
    location: Optional[str]
    url: Optional[str]
    salary: Optional[str]
    work_mode: Optional[str]
    source: Optional[str]
    status: Optional[str]              # display status (mapped to a pipeline column)
    raw_status: Optional[str]         # original value stored in the DB
    match_pct: Optional[float]
    llm_match_pct: Optional[float]
    job_description: Optional[str]
    email_date: Optional[str]
    status_updated_at: Optional[str]
    ignored: bool


class NoteIn(BaseModel):
    content: str


class NoteOut(BaseModel):
    id: int
    job_key: str
    content: str
    created_at: str
    updated_at: str


class ChecklistItemIn(BaseModel):
    text: str


class ChecklistItemUpdate(BaseModel):
    text: Optional[str] = None
    done: Optional[bool] = None


class ChecklistItemOut(BaseModel):
    id: int
    job_key: str
    text: str
    done: bool
    position: int


class ResumeOut(BaseModel):
    id: int
    name: str
    content_text: str
    file_name: Optional[str]
    mime_type: Optional[str]
    is_active: bool
    uploaded_at: str


class ResumeTextIn(BaseModel):
    name: Optional[str] = "My Resume"
    content_text: str


# --- AI compare ---------------------------------------------------------------

class CompareRequest(BaseModel):
    # Either reference a stored resume or paste text inline.
    resume_id: Optional[int] = None
    resume_text: Optional[str] = None


class KeywordChip(BaseModel):
    label: str
    matched: bool


class CompareResult(BaseModel):
    job_key: str
    match_score: int                  # 0-100
    matched_keywords: List[str]
    missing_keywords: List[str]
    keyword_chips: List[KeywordChip]
    interview_questions: List[str]
    resume_tips: List[str]
    summary: str
    source: str                       # "llm" | "heuristic-stub"


class StatsOut(BaseModel):
    total: int
    visible: int
    ignored: int
    by_status: dict
