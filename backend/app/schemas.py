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


class BulkStatus(BaseModel):
    job_keys: List[str]
    status: str


class WatchlistToggle(BaseModel):
    on: bool = True


class BulkWatchlist(BaseModel):
    job_keys: List[str]
    on: bool = True


class JobOut(BaseModel):
    job_key: str
    title: Optional[str]
    company: Optional[str]
    location: Optional[str]
    url: Optional[str]
    salary: Optional[str]
    work_mode: Optional[str]
    distance_miles: Optional[float]   # miles from home city (null = remote/unknown)
    source: Optional[str]
    status: Optional[str]              # display status (mapped to a pipeline column)
    raw_status: Optional[str]         # original value stored in the DB
    match_pct: Optional[float]
    llm_match_pct: Optional[float]     # initial score from ingestion
    semantic_score: Optional[float]   # offline sentence-transformers similarity
    compare_score: Optional[float]    # detailed "Compare with Resume" score
    compare_at: Optional[str]
    job_description: Optional[str]
    email_date: Optional[str]
    status_updated_at: Optional[str]
    ignored: bool
    mismatched: bool
    mismatch_reason: Optional[str]
    watchlist: bool                    # starred to revisit later


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
    # Resume source: inline text > referenced id > active resume.
    resume_id: Optional[int] = None
    resume_text: Optional[str] = None
    model: Optional[str] = None        # override the Gemini model for this run
    force: bool = False                # re-run even if a saved analysis exists


class CompareResult(BaseModel):
    job_key: str
    match_score: int                   # 0-100, contextual fit
    report_markdown: str               # full Markdown analysis (4 sections)
    used_job_description: bool          # was a real JD available for the analysis
    model: str                         # which model produced it
    source: str                        # "gemini" | "heuristic-stub"
    created_at: str
    cached: bool = False               # true if returned from saved analysis


class ModelsOut(BaseModel):
    enabled: bool                      # is a Gemini API key configured
    default: str
    models: List[str]


class StatsOut(BaseModel):
    total: int
    visible: int
    ignored: int
    mismatched: int = 0
    watchlist: int = 0
    by_status: dict


# --- Preferences / settings ---------------------------------------------------

class Settings(BaseModel):
    city: str = ""                       # the user's home city for distance
    max_distance_miles: Optional[float] = None
    salary_min: Optional[int] = None     # annual
    salary_max: Optional[int] = None
    min_match_score: Optional[int] = None
    title_keywords: List[str] = []       # keep jobs whose title has any of these
    exclude_companies: List[str] = []
    # Which LLM provider powers the career assistant: anthropic | gemini | openai.
    # None falls back to the AGENT_PROVIDER default.
    agent_provider: Optional[str] = None


class ApplyResult(BaseModel):
    evaluated: int
    moved_to_mismatched: int
    restored: int
    still_mismatched: int
    geocode_failures: int
