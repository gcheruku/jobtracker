"""Offline semantic resume<->JD matching: batch backfill + status."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlmodel import Session

from ..database import get_session
from ..services.semantic import (
    backend,
    backfill_status,
    eligible_count,
    is_available,
    run_backfill,
)

router = APIRouter(prefix="/api/semantic", tags=["semantic"])


@router.get("/status")
def status(saved_only: bool = False, session: Session = Depends(get_session)) -> dict:
    eligible = 0 if backfill_status.get("running") else eligible_count(session, saved_only=saved_only)
    return {**backfill_status, "available": is_available(), "backend": backend(), "eligible": eligible}


@router.post("/run")
def run(background_tasks: BackgroundTasks, recheck: bool = False, saved_only: bool = False) -> dict:
    """Score jobs without a match score (skips Inactive jobs). saved_only
    restricts to the Saved column. Expired postings are moved off the board.
    recheck=true also re-processes jobs already attempted."""
    if backfill_status.get("running"):
        return {"started": False, "detail": "A run is already in progress."}
    background_tasks.add_task(run_backfill, recheck, saved_only)
    return {"started": True}
