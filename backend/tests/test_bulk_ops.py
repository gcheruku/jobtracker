"""Regression tests for bulk skip / status-move.

Previously the UI fired one request per job, and a large selection (e.g. 234)
partially failed. These single-transaction endpoints must mark the WHOLE
selection in one go.
"""
import pytest
from fastapi import HTTPException
from sqlmodel import Session, SQLModel, select

from app.database import engine
from app.models import Job
from app.routers.jobs import bulk_ignore, bulk_status
from app.schemas import BulkKeys, BulkStatus


def _fresh_session(n: int) -> Session:
    """A session seeded with n Saved, non-ignored jobs (clean slate)."""
    SQLModel.metadata.create_all(engine)
    session = Session(engine)
    for j in session.exec(select(Job)).all():
        session.delete(j)
    session.commit()
    for i in range(n):
        session.add(
            Job(job_key=f"k{i}", title="Software Engineer", company="Acme",
                status="Saved", ignored=False)
        )
    session.commit()
    return session


def test_bulk_ignore_marks_entire_large_selection():
    with _fresh_session(234) as s:
        keys = [j.job_key for j in s.exec(select(Job)).all()]
        result = bulk_ignore(BulkKeys(job_keys=keys), s)
        assert result["ignored"] == 234
        assert all(j.ignored for j in s.exec(select(Job)).all())


def test_bulk_ignore_skips_missing_keys():
    with _fresh_session(3) as s:
        result = bulk_ignore(BulkKeys(job_keys=["k0", "nope", "k2"]), s)
        assert result["ignored"] == 2  # missing key ignored, no error


def test_bulk_status_moves_entire_selection():
    with _fresh_session(50) as s:
        keys = [j.job_key for j in s.exec(select(Job)).all()]
        result = bulk_status(BulkStatus(job_keys=keys, status="Applied"), s)
        assert result["updated"] == 50
        assert all(j.status == "Applied" for j in s.exec(select(Job)).all())


def test_bulk_status_rejects_invalid_status():
    with _fresh_session(2) as s:
        keys = [j.job_key for j in s.exec(select(Job)).all()]
        with pytest.raises(HTTPException) as exc:
            bulk_status(BulkStatus(job_keys=keys, status="Bogus"), s)
        assert exc.value.status_code == 400
