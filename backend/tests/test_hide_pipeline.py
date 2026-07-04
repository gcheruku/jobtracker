"""Tests for the search "hide handled" toggle.

The single UI toggle sets `hide_watchlist=True` and `hide_pipeline=True`
together: it drops jobs you've already triaged — starred (watchlisted) and
in-pipeline (Applied/Interviewing/Offer) — leaving only the untouched,
non-starred Saved candidate pool. The two flags are also exercised
independently here.
"""
from sqlmodel import Session, SQLModel, select

from app.database import engine
from app.models import Job
from app.routers.jobs import list_jobs


def _fresh_session() -> Session:
    SQLModel.metadata.create_all(engine)
    session = Session(engine)
    for j in session.exec(select(Job)).all():
        session.delete(j)
    session.commit()
    # One job per board status, plus a fresh (non-starred) Saved job.
    rows = [
        ("p_saved_new", "Saved", False),   # untriaged: survives "hide handled"
        ("p_saved_star", "Saved", True),   # starred -> hidden by hide_watchlist
        ("p_applied", "Applied", True),
        ("p_interview", "Interviewing", False),
        ("p_offer", "Offer", False),
    ]
    for key, status, star in rows:
        session.add(Job(job_key=key, title="Engineer", company="Acme",
                        status=status, ignored=False, mismatched=False, watchlist=star))
    session.commit()
    return session


def _list(session, **kw):
    base = dict(
        session=session, q=None, match="all", status=None, work_mode=None,
        min_salary=None, include_ignored=False, only_ignored=False,
        board_only=True, off_board=False, only_mismatched=False,
        watchlist=False, hide_watchlist=False, hide_pipeline=False, sort="recent",
    )
    base.update(kw)
    return list_jobs(**base)


def test_hide_pipeline_keeps_only_saved():
    with _fresh_session() as s:
        out = _list(s, hide_pipeline=True)
        assert {j.status for j in out} == {"Saved"}


def test_hide_watchlist_drops_starred():
    with _fresh_session() as s:
        out = _list(s, hide_watchlist=True)
        assert all(not j.watchlist for j in out)
        assert "p_saved_star" not in {j.job_key for j in out}


def test_hide_handled_keeps_only_untriaged_saved():
    # The combined toggle: non-starred Saved jobs only.
    with _fresh_session() as s:
        out = _list(s, hide_watchlist=True, hide_pipeline=True)
        assert [j.job_key for j in out] == ["p_saved_new"]


def test_no_flags_shows_all_board():
    with _fresh_session() as s:
        out = _list(s)
        assert {j.status for j in out} == {"Saved", "Applied", "Interviewing", "Offer"}
