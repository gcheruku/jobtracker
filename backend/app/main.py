"""FastAPI entrypoint.

Run from the backend/ directory:
    uvicorn app.main:app --reload --port 8000

Interactive OpenAPI docs are auto-generated at /docs and /redoc.
"""
from __future__ import annotations

import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from .config import CORS_ORIGINS, DATABASE_URL, INGEST_INTERVAL_HOURS, PIPELINE_STATUSES
from .database import init_db
from .logging_config import logger, setup_logging
from .routers import ai, ingest, jobs, resume, semantic, settings, stats
from .scheduler import start_scheduler, stop_scheduler

# Configure console logging before anything else emits a record.
setup_logging()

app = FastAPI(
    title="JobTrack API",
    version="1.0.0",
    description="Self-hosted job tracking dashboard API (FastAPI + SQLModel + SQLite).",
)

# The SPA calls /api same-origin via the nginx proxy, so CORS isn't needed in
# normal use; it's locked to localhost dev origins by default (override with
# JOBTRACKER_CORS_ORIGINS) instead of the old wildcard.
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,  # no cookies/credentials are used
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log one line per request: method, path, status, and duration."""
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        elapsed = (time.perf_counter() - start) * 1000
        logger.exception(
            "%s %s -> 500 ERROR in %.1fms", request.method, request.url.path, elapsed
        )
        raise
    elapsed = (time.perf_counter() - start) * 1000
    query = f"?{request.url.query}" if request.url.query else ""
    logger.info(
        "%s %s%s -> %d in %.1fms",
        request.method,
        request.url.path,
        query,
        response.status_code,
        elapsed,
    )
    return response


@app.on_event("startup")
def _startup() -> None:
    logger.info("Starting JobTrack API")
    logger.info("Database: %s", DATABASE_URL)
    logger.info("CORS origins: %s", CORS_ORIGINS)
    logger.info("Pipeline: %s", " | ".join(PIPELINE_STATUSES))
    # Non-destructive: adds new columns/tables to the existing jobs.db.
    init_db()
    start_scheduler()
    logger.info("Ingest scheduled every %.1fh", INGEST_INTERVAL_HOURS)

    # Backfill per-job distances in the background (geocoding is cached and rate
    # limited, so this can take a while on first run; never blocks startup).
    import threading

    from .services.distance import backfill_distances

    threading.Thread(target=backfill_distances, name="distance-backfill", daemon=True).start()
    logger.info("Startup complete — docs at /docs")


@app.on_event("shutdown")
def _shutdown() -> None:
    stop_scheduler()


@app.get("/api/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok", "pipeline": PIPELINE_STATUSES}


app.include_router(jobs.router)
app.include_router(resume.router)
app.include_router(ai.router)
app.include_router(stats.router)
app.include_router(ingest.router)
app.include_router(settings.router)
app.include_router(semantic.router)
