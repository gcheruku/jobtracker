"""Engine, session helper, and a non-destructive startup migration.

The migration:
  1. Adds the new columns (`ignored`, `work_mode`) to the existing `jobs`
     table only if they don't already exist (ALTER TABLE ADD COLUMN is safe and
     additive — no rows are touched).
  2. Creates the new tables (note, resume, checklist_item) via create_all,
     which never drops or alters existing tables.
"""
from __future__ import annotations

from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine

from . import models  # noqa: F401  (ensures models register on SQLModel.metadata)
from .config import DATABASE_URL
from .logging_config import logger

# check_same_thread=False is required for SQLite under FastAPI's threadpool.
engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
)


def _existing_columns(conn, table: str) -> set[str]:
    rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
    return {r[1] for r in rows}


def _add_column_if_missing(conn, table: str, column: str, ddl_type: str) -> None:
    if column not in _existing_columns(conn, table):
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type}"))


def init_db() -> None:
    """Idempotent: safe to call on every startup.

    Bootstraps a fresh database (creates the SQLModel tables + the key/value
    `meta` table) and additively migrates an existing one. create_all leaves any
    table that already exists untouched, so an existing jobs.db is preserved.
    """
    # Bootstrap for a clean clone: meta isn't a SQLModel model, so create it here.
    with engine.begin() as conn:
        conn.execute(
            text("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")
        )
    # Create jobs/note/checklist_item/resume/geo_cache if absent.
    SQLModel.metadata.create_all(engine)

    with engine.begin() as conn:
        before = _existing_columns(conn, "jobs")
        # Additive columns for older databases that predate them.
        _add_column_if_missing(conn, "jobs", "ignored", "INTEGER DEFAULT 0")
        _add_column_if_missing(conn, "jobs", "work_mode", "TEXT")
        _add_column_if_missing(conn, "jobs", "distance_miles", "REAL")
        _add_column_if_missing(conn, "jobs", "compare_score", "REAL")
        _add_column_if_missing(conn, "jobs", "compare_analysis", "TEXT")
        _add_column_if_missing(conn, "jobs", "compare_at", "TEXT")
        _add_column_if_missing(conn, "jobs", "mismatched", "INTEGER DEFAULT 0")
        conn.execute(text("UPDATE jobs SET mismatched = 0 WHERE mismatched IS NULL"))
        _add_column_if_missing(conn, "jobs", "mismatch_reason", "TEXT")
        _add_column_if_missing(conn, "jobs", "semantic_score", "REAL")
        _add_column_if_missing(conn, "jobs", "semantic_at", "TEXT")
        _add_column_if_missing(conn, "jobs", "semantic_attempted_at", "TEXT")
        # Normalize any NULL ignored values left by older rows.
        conn.execute(text("UPDATE jobs SET ignored = 0 WHERE ignored IS NULL"))

        # A '/' in a job_key breaks FastAPI path-param routing (it 404s every
        # path-based action). Sanitize any that exist so external ingesters that
        # use raw titles in keys can't reintroduce broken rows. OR IGNORE skips
        # the rare case where sanitizing would collide with an existing key.
        for tbl in ("note", "checklist_item", "jobs"):
            conn.execute(
                text(
                    f"UPDATE OR IGNORE {tbl} SET job_key = replace(job_key, '/', '-') "
                    "WHERE job_key LIKE '%/%'"
                )
            )

        added = _existing_columns(conn, "jobs") - before
        total = conn.execute(text("SELECT COUNT(*) FROM jobs")).scalar()
        skipped = conn.execute(
            text("SELECT COUNT(*) FROM jobs WHERE ignored = 1")
        ).scalar()

    if added:
        logger.info("Migration: added columns to jobs: %s", ", ".join(sorted(added)))
    logger.info("DB ready: %d jobs (%d skipped)", total, skipped)


def get_session():
    with Session(engine) as session:
        yield session
