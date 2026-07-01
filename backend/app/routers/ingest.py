"""Manual ingest trigger + status, for the UI 'Fetch alerts' button."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Query

from ..config import (
    GMAIL_LABEL,
    GOOGLE_API_KEY,
    INGEST_INTERVAL_HOURS,
    INGEST_MAX_MESSAGES_ALL,
)
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
def trigger_ingest(
    background_tasks: BackgroundTasks,
    since_epoch: Optional[int] = Query(
        None, description="Unix seconds; fetch alerts delivered after this time"
    ),
    fetch_all: bool = Query(
        False, description="Scan the entire label (ignores the watermark)"
    ),
) -> dict:
    """Kick off a fetch in the background and return immediately.

    - default: incremental fetch from the watermark.
    - since_epoch: reprocess emails delivered after a chosen start date.
    - fetch_all: scan the whole label.

    Poll GET /api/ingest/status for progress/results.
    """
    if status.get("running"):
        return {"started": False, "detail": "An ingest is already running."}

    # Mark running synchronously — BackgroundTasks execute AFTER the response is
    # sent, so without this there's a window where status.running is still False
    # and the UI's first poll concludes the run already finished.
    status["running"] = True
    status["phase"] = "starting"
    status["scored_so_far"] = 0

    if fetch_all:
        background_tasks.add_task(
            run_ingest, max_messages=INGEST_MAX_MESSAGES_ALL, since_epoch=0
        )
    elif since_epoch is not None:
        background_tasks.add_task(
            run_ingest, max_messages=INGEST_MAX_MESSAGES_ALL, since_epoch=since_epoch
        )
    else:
        background_tasks.add_task(run_ingest)
    return {"started": True}
