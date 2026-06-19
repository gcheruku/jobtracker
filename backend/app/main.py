"""FastAPI entrypoint.

Run from the backend/ directory:
    uvicorn app.main:app --reload --port 8000

Interactive OpenAPI docs are auto-generated at /docs and /redoc.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import CORS_ORIGINS, PIPELINE_STATUSES
from .database import init_db
from .routers import ai, jobs, resume, stats

app = FastAPI(
    title="JobTrack API",
    version="1.0.0",
    description="Self-hosted job tracking dashboard API (FastAPI + SQLModel + SQLite).",
)

# Open CORS so the frontend can connect from any origin/device, per the spec.
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,  # wildcard origins require credentials off
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    # Non-destructive: adds new columns/tables to the existing jobs.db.
    init_db()


@app.get("/api/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok", "pipeline": PIPELINE_STATUSES}


app.include_router(jobs.router)
app.include_router(resume.router)
app.include_router(ai.router)
app.include_router(stats.router)
