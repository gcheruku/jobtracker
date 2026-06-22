"""Per-job distance (miles) from the user's home city, for the distance filter.

Distances are geocoded (cached via geo_cache) and stored on jobs.distance_miles.
Remote or ungeocodable jobs stay NULL (and are excluded when a distance filter
is active). Backfill is idempotent — it only fills rows that are still NULL.
"""
from __future__ import annotations

from typing import Optional, Tuple

from sqlmodel import Session, select

from ..database import engine
from ..logging_config import logger
from ..models import Job
from .geo import geocode, haversine_miles, is_remote
from .preferences import _geo_query, _home_state, load_settings


def compute_distance_miles(
    session: Session,
    location: Optional[str],
    user_coord: Optional[Tuple[float, float]],
    home_state: str,
) -> Optional[float]:
    """Miles from the home coordinate to a job location, or None when the job is
    remote/ungeocodable or the home city is unknown."""
    if user_coord is None or is_remote(location):
        return None
    coord = geocode(session, _geo_query(location or "", home_state))
    if not coord:
        return None
    return round(haversine_miles(user_coord, coord), 1)


def backfill_distances(limit: Optional[int] = None) -> dict:
    """Fill distance_miles for jobs that don't have it yet. Safe to call often;
    geocoding is cached so repeat runs are cheap."""
    with Session(engine) as session:
        s = load_settings(session)
        if not s.city:
            return {"skipped": "no home city set"}
        user_coord = geocode(session, s.city)
        if user_coord is None:
            return {"skipped": "home city not geocodable"}
        home_state = _home_state(s.city)

        stmt = select(Job).where(Job.distance_miles == None)  # noqa: E711
        if limit:
            stmt = stmt.limit(limit)
        jobs = session.exec(stmt).all()

        filled = 0
        for job in jobs:
            d = compute_distance_miles(session, job.location, user_coord, home_state)
            if d is not None:
                job.distance_miles = d
                session.add(job)
                filled += 1
        session.commit()
        logger.info("Distance backfill: filled %d of %d candidates", filled, len(jobs))
        return {"candidates": len(jobs), "filled": filled}
