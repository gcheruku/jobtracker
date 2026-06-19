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
    """Idempotent: safe to call on every startup."""
    with engine.begin() as conn:
        # Additive columns on the existing jobs table.
        _add_column_if_missing(conn, "jobs", "ignored", "INTEGER DEFAULT 0")
        _add_column_if_missing(conn, "jobs", "work_mode", "TEXT")
        # Normalize any NULL ignored values left by older rows.
        conn.execute(text("UPDATE jobs SET ignored = 0 WHERE ignored IS NULL"))

    # Create the brand-new tables; existing tables are left untouched.
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
