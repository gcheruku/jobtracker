"""Geocoding (OpenStreetMap/Nominatim) with DB caching + distance helpers.

Each unique location string is geocoded once and cached in the geo_cache table,
so applying preferences across many jobs stays within Nominatim's usage policy.
"""
from __future__ import annotations

import math
import time
from typing import Optional, Tuple

import requests
from sqlmodel import Session

from ..logging_config import logger
from ..models import GeoCache

_UA = {"User-Agent": "JobTrack/1.0 (self-hosted job tracker)"}
_NOMINATIM = "https://nominatim.openstreetmap.org/search"

# Location strings that mean "no fixed location" -> distance check doesn't apply.
_REMOTE_MARKERS = ("remote", "anywhere", "work from home", "wfh")
_NATIONWIDE = ("united states", "usa", "u.s.", "nationwide")
# Junk location values we should not try to geocode.
_JUNK = ("apply with", "see all", "multiple", "various")


def is_remote(location: Optional[str]) -> bool:
    """Remote/nationwide jobs are exempt from the distance check."""
    low = (location or "").strip().lower()
    if not low:
        return False
    return any(m in low for m in _REMOTE_MARKERS) or low in _NATIONWIDE


def _is_geocodable(location: Optional[str]) -> bool:
    low = (location or "").strip().lower()
    if len(low) < 3 or is_remote(location):
        return False
    return not any(j in low for j in _JUNK)


def haversine_miles(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    R = 3958.8
    (la1, lo1), (la2, lo2) = a, b
    rad = math.radians
    dlat, dlon = rad(la2 - la1), rad(lo2 - lo1)
    h = math.sin(dlat / 2) ** 2 + math.cos(rad(la1)) * math.cos(rad(la2)) * math.sin(dlon / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def geocode(session: Session, location: Optional[str]) -> Optional[Tuple[float, float]]:
    """Return (lat, lon) for a location, using the cache. None if not found."""
    if not _is_geocodable(location):
        return None
    key = location.strip()
    cached = session.get(GeoCache, key)
    if cached:
        return (cached.lat, cached.lon) if cached.found and cached.lat is not None else None

    coord: Optional[Tuple[float, float]] = None
    try:
        time.sleep(1.0)  # respect Nominatim's 1 req/sec policy
        resp = requests.get(
            _NOMINATIM,
            params={"q": key, "format": "json", "limit": 1, "countrycodes": "us"},
            headers=_UA,
            timeout=20,
        )
        data = resp.json() if resp.status_code == 200 else []
        if data:
            coord = (float(data[0]["lat"]), float(data[0]["lon"]))
    except Exception as exc:
        logger.warning("Geocode failed for %r: %s", key, exc)
        return None  # don't cache transient failures

    session.merge(
        GeoCache(
            query=key,
            lat=coord[0] if coord else None,
            lon=coord[1] if coord else None,
            found=coord is not None,
        )
    )
    session.commit()
    return coord
