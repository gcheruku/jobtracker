"""Tool surface for the job-pipeline agent.

Each tool is a thin, read-only adapter over the existing services/DB — the agent
plans which to call; the runner executes them. Keeping them read-only means no
action is destructive, so v1 needs no human-in-the-loop approval gate (that's
the natural next layer: promote write tools like set_status/skip behind an
approval queue).

A tool = a JSON schema (sent to Claude) + an executor `(args) -> dict` (run by
the runner). `TOOLS` is the schema list; `EXECUTORS` maps name -> callable.
"""
from __future__ import annotations

from typing import Any, Callable

from sqlmodel import Session, select

from ..database import engine
from ..models import Job
from ..services.ai import compute_fit
from ..services.resume_loader import resume_text

# --- executors ---------------------------------------------------------------

_JOB_FIELDS = (
    "job_key", "title", "company", "location", "source", "status",
    "salary", "work_mode", "url",
)


def _job_summary(j: Job) -> dict:
    """Compact, token-cheap view of a job for list results."""
    match = j.llm_match_pct if j.llm_match_pct is not None else j.match_pct
    return {
        **{f: getattr(j, f) for f in _JOB_FIELDS},
        "status": "Skipped" if j.ignored else (j.status or "Saved"),
        "match_pct": round(match) if match is not None else None,
        "has_description": bool(j.job_description),
    }


def search_jobs(args: dict) -> dict:
    """Filter the pipeline by free-text + status/source; return compact rows."""
    q = (args.get("query") or "").strip().lower()
    status = (args.get("status") or "").strip().lower()
    source = (args.get("source") or "").strip().lower()
    limit = max(1, min(int(args.get("limit") or 10), 50))

    with Session(engine) as session:
        rows = session.exec(select(Job)).all()

    out = []
    for j in rows:
        hay = " ".join(
            str(getattr(j, f) or "") for f in ("title", "company", "location")
        ).lower()
        if q and q not in hay:
            continue
        eff_status = ("skipped" if j.ignored else (j.status or "saved")).lower()
        if status and status != eff_status:
            continue
        if source and source != (j.source or "").lower():
            continue
        out.append(j)

    # Best matches first, then most recent.
    out.sort(
        key=lambda j: (
            -(j.llm_match_pct or j.match_pct or 0),
            -(j.email_epoch or 0),
        )
    )
    return {"count": len(out), "results": [_job_summary(j) for j in out[:limit]]}


def get_job(args: dict) -> dict:
    """Full detail for one job, including the description (capped for tokens)."""
    key = args.get("job_key") or ""
    with Session(engine) as session:
        j = session.get(Job, key)
        if not j:
            return {"error": f"No job with job_key={key!r}"}
        desc = j.job_description or ""
        return {
            **_job_summary(j),
            "job_description": desc[:8000] + ("… [truncated]" if len(desc) > 8000 else ""),
            "description_chars": len(desc),
        }


def get_pipeline_stats(_args: dict) -> dict:
    """Counts by pipeline status, plus skipped/total — the board at a glance."""
    with Session(engine) as session:
        rows = session.exec(select(Job)).all()
    by_status: dict[str, int] = {}
    skipped = 0
    for j in rows:
        if j.ignored:
            skipped += 1
            continue
        s = j.status or "Saved"
        by_status[s] = by_status.get(s, 0) + 1
    return {"total": len(rows), "skipped": skipped, "by_status": by_status}


def compare_resume_to_job(args: dict) -> dict:
    """Run the existing resume↔JD analysis for one job (Gemini-backed)."""
    key = args.get("job_key") or ""
    with Session(engine) as session:
        j = session.get(Job, key)
        if not j:
            return {"error": f"No job with job_key={key!r}"}
        header = f"{j.title or ''} at {j.company or ''}\n{j.location or ''}\n{j.salary or ''}"
        job_text = f"{header}\n\n{j.job_description or ''}".strip()
    resume = resume_text()
    if not resume:
        return {"error": "No resume is configured to compare against."}
    try:
        result = compute_fit(job_text, resume)
    except Exception as exc:  # surface to the model so it can explain/recover
        return {"error": f"Comparison failed: {exc}"}
    return {
        "match_score": result.get("match_score"),
        "report_markdown": result.get("report_markdown"),
        "used_job_description": bool(j.job_description),
    }


EXECUTORS: dict[str, Callable[[dict], dict]] = {
    "search_jobs": search_jobs,
    "get_job": get_job,
    "get_pipeline_stats": get_pipeline_stats,
    "compare_resume_to_job": compare_resume_to_job,
}


# --- schemas (sent to Claude) -------------------------------------------------

TOOLS: list[dict[str, Any]] = [
    {
        "name": "search_jobs",
        "description": (
            "Search the user's job pipeline by free text (matches title/company/"
            "location) and optionally filter by pipeline status or source. Returns "
            "compact rows sorted by match score then recency. Call this first when "
            "the user asks about 'my jobs', a company, a role, or a category."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Free-text filter over title/company/location."},
                "status": {
                    "type": "string",
                    "description": "Pipeline status to filter by (e.g. Saved, Applied, Interviewing, Offer, Rejected, Expired, Skipped).",
                },
                "source": {"type": "string", "description": "Board source: Indeed, LinkedIn, Glassdoor, Dice, Manual."},
                "limit": {"type": "integer", "description": "Max rows to return (default 10, max 50)."},
            },
        },
    },
    {
        "name": "get_job",
        "description": (
            "Fetch full details for one job by its job_key, including the job "
            "description. Use after search_jobs when you need the description or "
            "specifics. job_key comes from search_jobs results."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"job_key": {"type": "string", "description": "The job's unique key from search_jobs."}},
            "required": ["job_key"],
        },
    },
    {
        "name": "get_pipeline_stats",
        "description": "Get counts of jobs by pipeline status (plus skipped/total). Use for 'how many', overview, or progress questions.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "compare_resume_to_job",
        "description": (
            "Analyze how well the user's resume fits a specific job, returning a "
            "match score and a markdown report. Use when the user asks whether a "
            "role is a good fit, or to compare/rank a job against their resume. "
            "Needs the job_key from search_jobs."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"job_key": {"type": "string", "description": "The job's unique key from search_jobs."}},
            "required": ["job_key"],
        },
    },
]
