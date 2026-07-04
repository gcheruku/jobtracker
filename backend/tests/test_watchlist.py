"""Tests for the watchlist (revisit-later) star flag."""
import pytest
from fastapi import HTTPException
from sqlmodel import Session, SQLModel, select

from app.database import engine
from app.models import Job
from app.routers.jobs import bulk_watchlist, list_jobs, set_watchlist
from app.schemas import BulkWatchlist, WatchlistToggle


def _fresh_session(n: int) -> Session:
    SQLModel.metadata.create_all(engine)
    session = Session(engine)
    for j in session.exec(select(Job)).all():
        session.delete(j)
    session.commit()
    for i in range(n):
        session.add(Job(job_key=f"w{i}", title="Engineer", company="Acme",
                        status="Saved", ignored=False, watchlist=False))
    session.commit()
    return session


def test_set_watchlist_toggles_flag():
    with _fresh_session(1) as s:
        out = set_watchlist("w0", WatchlistToggle(on=True), s)
        assert out.watchlist is True
        assert s.get(Job, "w0").watchlist is True
        out = set_watchlist("w0", WatchlistToggle(on=False), s)
        assert out.watchlist is False


def test_set_watchlist_missing_job_404():
    with _fresh_session(0) as s:
        with pytest.raises(HTTPException) as exc:
            set_watchlist("nope", WatchlistToggle(on=True), s)
        assert exc.value.status_code == 404


def test_bulk_watchlist_and_filter():
    with _fresh_session(10) as s:
        keys = [j.job_key for j in s.exec(select(Job)).all()][:6]
        res = bulk_watchlist(BulkWatchlist(job_keys=keys, on=True), s)
        assert res["updated"] == 6
        # The watchlist filter returns exactly the starred jobs.
        starred = list_jobs(
            session=s, q=None, match="all", status=None, work_mode=None,
            min_salary=None, include_ignored=False, only_ignored=False,
            board_only=False, off_board=False, only_mismatched=False,
            watchlist=True, hide_watchlist=False, hide_pipeline=False, sort="recent",
        )
        assert len(starred) == 6
        assert all(j.watchlist for j in starred)
