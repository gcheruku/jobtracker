"""Manual ingest trigger + status, for the UI 'Fetch alerts' button."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks

from ..config import GMAIL_LABEL, GOOGLE_API_KEY, INGEST_INTERVAL_HOURS
from ..services.ingest import run_ingest, status

router = APIRouter(prefix="/api/ingest", tags=["ingest"])


@router.get("/status")
def ingest_status() -> dict:
    return {
        **status,
        "label": GMAIL_LABEL,
        "interval_hours": INGEST_INTERVAL_HOURS,
        "gemini_enabled": bool(GOOGLE_API_KEY),
    }


@router.post("/run")
def trigger_ingest(background_tasks: BackgroundTasks) -> dict:
    """Kick off a fetch in the background and return immediately.

    Poll GET /api/ingest/status for progress/results.
    """
    if status.get("running"):
        return {"started": False, "detail": "An ingest is already running."}
    background_tasks.add_task(run_ingest)
    return {"started": True}
