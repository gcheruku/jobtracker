"""User preferences (salary/location/distance/match/keywords) + apply-to-board."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlmodel import Session

from ..database import get_session
from ..schemas import Settings
from ..services.preferences import apply_status, load_settings, run_apply, save_settings

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("", response_model=Settings)
def get_settings(session: Session = Depends(get_session)) -> Settings:
    return load_settings(session)


@router.put("", response_model=Settings)
def put_settings(payload: Settings, session: Session = Depends(get_session)) -> Settings:
    save_settings(session, payload)
    return payload


@router.post("/apply")
def apply(background_tasks: BackgroundTasks, session: Session = Depends(get_session)) -> dict:
    """Re-evaluate the board against saved settings (runs in the background)."""
    if apply_status.get("running"):
        return {"started": False, "detail": "An apply is already running."}
    settings = load_settings(session)
    background_tasks.add_task(run_apply, settings)
    return {"started": True}


@router.get("/apply-status")
def apply_state() -> dict:
    return apply_status
