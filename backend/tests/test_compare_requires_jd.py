"""Compare with Resume refuses to run without a real job description.

Without a JD the model only sees the title/company header, so it returns a
confident-looking but meaningless score — and bills for it. Both entry points
(the HTTP endpoint the UI clicks and the agent tool) must bail out first.
"""
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, select

from app.agent.tools import compare_resume_to_job
from app.database import engine
from app.main import app
from app.models import Job

client = TestClient(app)

REAL_JD = "We are hiring a backend engineer. " * 20  # comfortably over the min


def _reset():
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        for j in s.exec(select(Job)).all():
            s.delete(j)
        s.commit()


def _add(job_key: str, *, description: str | None = None, url: str | None = None):
    with Session(engine) as s:
        s.add(Job(job_key=job_key, title="Engineer", company="Acme", url=url,
                  job_description=description, status="Saved",
                  ignored=False, mismatched=False, watchlist=False))
        s.commit()


def test_endpoint_refuses_when_no_description_and_no_url():
    _reset()
    _add("no-jd")
    with patch("app.routers.ai.compute_fit") as fit, \
         patch("app.routers.ai._resolve_resume", return_value="my resume"):
        r = client.post("/api/ai/compare/no-jd", json={"force": True})
    assert r.status_code == 422
    assert "job description" in r.json()["detail"].lower()
    fit.assert_not_called()  # no paid call was made


def test_endpoint_refuses_when_the_stored_description_is_too_short():
    _reset()
    _add("stub-jd", description="Great opportunity!")
    with patch("app.routers.ai.compute_fit") as fit, \
         patch("app.routers.ai._resolve_resume", return_value="my resume"):
        r = client.post("/api/ai/compare/stub-jd", json={"force": True})
    assert r.status_code == 422
    fit.assert_not_called()


def test_endpoint_refuses_when_the_fetch_comes_back_empty():
    _reset()
    _add("fetch-fails", url="https://example.com/job/1")
    with patch("app.routers.ai.fetch_job_description", return_value="") as fetch, \
         patch("app.routers.ai.compute_fit") as fit, \
         patch("app.routers.ai._resolve_resume", return_value="my resume"):
        r = client.post("/api/ai/compare/fetch-fails", json={"force": True})
    assert r.status_code == 422
    fetch.assert_called_once()  # we still tried the posting first
    fit.assert_not_called()


def test_endpoint_runs_once_a_description_is_fetched():
    _reset()
    _add("fetch-works", url="https://example.com/job/2")
    fake = {"match_score": 80, "report_markdown": "# ok", "source": "gemini",
            "model": "gemini-test"}
    with patch("app.routers.ai.fetch_job_description", return_value=REAL_JD), \
         patch("app.routers.ai.compute_fit", return_value=fake) as fit, \
         patch("app.routers.ai._resolve_resume", return_value="my resume"):
        r = client.post("/api/ai/compare/fetch-works", json={"force": True})
    assert r.status_code == 200
    assert r.json()["used_job_description"] is True
    fit.assert_called_once()
    # The fetched description is persisted for next time.
    with Session(engine) as s:
        assert s.get(Job, "fetch-works").job_description == REAL_JD


def test_agent_tool_refuses_without_a_description():
    _reset()
    _add("agent-no-jd")
    with patch("app.agent.tools.compute_fit") as fit:
        out = compare_resume_to_job({"job_key": "agent-no-jd"})
    assert "error" in out
    assert "job description" in out["error"].lower()
    fit.assert_not_called()
