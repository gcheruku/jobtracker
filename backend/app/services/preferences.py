"""User preferences: storage, job matching, and applying them to the board.

A job is moved to "mismatched" only when it CLEARLY violates a setting; jobs with
unknown salary/location/score stay on the board (lenient). Distance applies only
to non-remote jobs.
"""
from __future__ import annotations

import json
import re
import threading
from datetime import datetime, timezone
from typing import Optional, Tuple

from sqlalchemy import text
from sqlmodel import Session, select

from ..config import STATUS_DISPLAY_MAP
from ..database import engine
from ..logging_config import logger
from ..models import Job
from ..schemas import Settings
from .geo import geocode, haversine_miles, is_remote

_PREF_KEY = "preferences"
_HOURS_PER_YEAR = 2080
_DAYS_PER_YEAR = 260


# --- storage ------------------------------------------------------------------

def load_settings(session: Session) -> Settings:
    row = session.exec(
        text("SELECT value FROM meta WHERE key=:k").bindparams(k=_PREF_KEY)
    ).first()
    if row and row[0]:
        try:
            return Settings(**json.loads(row[0]))
        except Exception:
            pass
    return Settings()


def save_settings(session: Session, settings: Settings) -> None:
    session.exec(
        text(
            "INSERT INTO meta(key,value) VALUES(:k,:v) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value"
        ).bindparams(k=_PREF_KEY, v=settings.model_dump_json())
    )
    session.commit()


# --- salary parsing -----------------------------------------------------------

def parse_salary_annual(salary: Optional[str]) -> Optional[Tuple[int, int]]:
    """Return (low, high) annualized salary, or None if unparseable."""
    if not salary:
        return None
    nums = [float(n.replace(",", "")) for n in re.findall(r"[\d,]+(?:\.\d+)?", salary)]
    nums = [n for n in nums if n > 0]
    if not nums:
        return None
    low = salary.lower()
    factor = _HOURS_PER_YEAR if "hour" in low else _DAYS_PER_YEAR if "day" in low else 1
    scaled = [int(n * factor) for n in nums]
    return min(scaled), max(scaled)


# --- matching -----------------------------------------------------------------

def job_matches(
    session: Session, job: Job, s: Settings, user_coord: Optional[Tuple[float, float]]
) -> Tuple[bool, str]:
    """(matches, reason_if_not). Lenient: unknown data does not disqualify."""
    # Salary
    if s.salary_min or s.salary_max:
        rng = parse_salary_annual(job.salary)
        if rng:
            jlo, jhi = rng
            if s.salary_min and jhi < s.salary_min:
                return False, f"salary below ${s.salary_min:,}"
            if s.salary_max and jlo > s.salary_max:
                return False, f"salary above ${s.salary_max:,}"

    # Distance (non-remote only)
    if s.city and s.max_distance_miles and user_coord and not is_remote(job.location):
        coord = geocode(session, job.location)
        if coord:
            miles = haversine_miles(user_coord, coord)
            if miles > s.max_distance_miles:
                return False, f"{round(miles)} mi away"

    # Minimum match score
    if s.min_match_score:
        score = job.compare_score or job.llm_match_pct or job.match_pct
        if score is not None and score < s.min_match_score:
            return False, f"match {round(score)}% < {s.min_match_score}%"

    # Title keywords (keep if title has ANY)
    if s.title_keywords:
        title = (job.title or "").lower()
        if not any(k.strip().lower() in title for k in s.title_keywords if k.strip()):
            return False, "title keyword"

    # Excluded companies
    if s.exclude_companies:
        company = (job.company or "").lower()
        if any(x.strip().lower() in company for x in s.exclude_companies if x.strip()):
            return False, "excluded company"

    return True, ""


def _is_saved(job: Job) -> bool:
    return STATUS_DISPLAY_MAP.get(job.status or "", job.status or "Saved") == "Saved"


def apply_preferences(session: Session, s: Settings) -> dict:
    """Re-evaluate the Saved pile + currently-mismatched jobs against settings.

    Tracked jobs (Applied/Interviewing/Offer), Rejected/Expired, and skipped
    (ignored) jobs are left untouched.
    """
    user_coord = geocode(session, s.city) if s.city else None
    geocode_failures = 0
    if s.city and user_coord is None:
        logger.warning("Could not geocode home city %r — distance disabled", s.city)
        geocode_failures += 1

    candidates = [
        j
        for j in session.exec(select(Job)).all()
        if not j.ignored and (j.mismatched or _is_saved(j))
    ]

    summary = {
        "evaluated": len(candidates),
        "moved_to_mismatched": 0,
        "restored": 0,
        "still_mismatched": 0,
        "geocode_failures": geocode_failures,
    }
    for job in candidates:
        matches, _ = job_matches(session, job, s, user_coord)
        was = bool(job.mismatched)
        now = not matches
        if now and not was:
            summary["moved_to_mismatched"] += 1
        elif not now and was:
            summary["restored"] += 1
        elif now and was:
            summary["still_mismatched"] += 1
        job.mismatched = now
        session.add(job)
    session.commit()
    logger.info("Applied preferences: %s", summary)
    return summary


# --- background runner (apply can take a while on first geocoding) ------------

_apply_lock = threading.Lock()
apply_status: dict = {
    "running": False, "last_summary": None, "last_error": None, "last_run_iso": None
}


def run_apply(settings: Settings) -> None:
    if not _apply_lock.acquire(blocking=False):
        logger.info("Apply already running; skipping")
        return
    apply_status.update(running=True, last_error=None)
    try:
        with Session(engine) as session:
            apply_status["last_summary"] = apply_preferences(session, settings)
        apply_status["last_run_iso"] = datetime.now(timezone.utc).isoformat()
    except Exception as exc:
        logger.exception("Apply preferences failed")
        apply_status["last_error"] = str(exc)
    finally:
        apply_status["running"] = False
        _apply_lock.release()
