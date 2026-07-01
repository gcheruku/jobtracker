"""Dashboard metrics + recent activity for the top metric cards and activity log."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from ..config import PIPELINE_STATUSES, STATUS_DISPLAY_MAP
from ..database import get_session
from ..models import Job
from ..schemas import StatsOut

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("", response_model=StatsOut)
def stats(session: Session = Depends(get_session)):
    jobs = session.exec(select(Job)).all()
    by_status = {s: 0 for s in PIPELINE_STATUSES}
    ignored = 0
    mismatched = 0
    watchlist = 0
    visible = 0
    for j in jobs:
        if j.watchlist and not j.ignored:
            watchlist += 1  # counted independently of pipeline status
        if j.ignored:
            ignored += 1
            continue
        if j.mismatched:
            mismatched += 1
            continue
        visible += 1
        disp = STATUS_DISPLAY_MAP.get(j.status or "", j.status) or PIPELINE_STATUSES[0]
        by_status[disp] = by_status.get(disp, 0) + 1
    return StatsOut(
        total=len(jobs),
        visible=visible,
        ignored=ignored,
        mismatched=mismatched,
        watchlist=watchlist,
        by_status=by_status,
    )


@router.get("/activity")
def activity(limit: int = 10, session: Session = Depends(get_session)) -> List[dict]:
    """Most recently touched (status-updated) visible jobs — the activity feed."""
    jobs = session.exec(
        select(Job).where((Job.ignored == False) | (Job.ignored == None))  # noqa: E711,E712
    ).all()
    jobs = [j for j in jobs if j.status_updated_at]
    jobs.sort(key=lambda j: j.status_updated_at or "", reverse=True)
    return [
        {
            "job_key": j.job_key,
            "title": j.title,
            "company": j.company,
            "status": STATUS_DISPLAY_MAP.get(j.status or "", j.status),
            "at": j.status_updated_at,
        }
        for j in jobs[:limit]
    ]
