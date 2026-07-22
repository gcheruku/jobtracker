"""Per-company candidate-portal URL.

The URL is stored per-company (normalized name), so setting it on one job makes
it show up on every job at the same company. Exercised end-to-end through the API.
"""
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, select

from app.database import engine
from app.main import app
from app.models import CompanyPortal, Job

client = TestClient(app)

PORTAL = "https://careers.acme.com/candidate/home"


def _reset():
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        for j in s.exec(select(Job)).all():
            s.delete(j)
        for p in s.exec(select(CompanyPortal)).all():
            s.delete(p)
        s.commit()


def _add(job_key: str, company: str) -> None:
    with Session(engine) as s:
        s.add(Job(job_key=job_key, title="Engineer", company=company,
                  status="Saved", ignored=False, mismatched=False, watchlist=False))
        s.commit()


def test_set_portal_is_shared_across_same_company_jobs():
    _reset()
    _add("acme-1", "Acme Corp")
    _add("acme-2", "Acme Corp")
    _add("other-1", "Globex")

    r = client.put("/api/jobs/acme-1/portal", json={"portal_url": PORTAL})
    assert r.status_code == 200
    assert r.json()["portal_url"] == PORTAL

    # The second Acme job inherits the same URL without ever being touched.
    assert client.get("/api/jobs/acme-2").json()["portal_url"] == PORTAL
    # A different company is unaffected.
    assert client.get("/api/jobs/other-1").json()["portal_url"] is None


def test_portal_key_ignores_case_and_whitespace():
    _reset()
    _add("a", "Acme  Corp")     # doubled space
    _add("b", "acme corp")      # lowercase, single space

    client.put("/api/jobs/a/portal", json={"portal_url": PORTAL})
    assert client.get("/api/jobs/b").json()["portal_url"] == PORTAL


def test_list_jobs_includes_portal_url():
    _reset()
    _add("acme-1", "Acme Corp")
    client.put("/api/jobs/acme-1/portal", json={"portal_url": PORTAL})

    rows = client.get("/api/jobs").json()
    assert any(j["job_key"] == "acme-1" and j["portal_url"] == PORTAL for j in rows)


def test_update_and_clear_portal():
    _reset()
    _add("acme-1", "Acme Corp")
    _add("acme-2", "Acme Corp")
    client.put("/api/jobs/acme-1/portal", json={"portal_url": PORTAL})

    new_url = "https://careers.acme.com/login"
    client.put("/api/jobs/acme-2/portal", json={"portal_url": new_url})
    assert client.get("/api/jobs/acme-1").json()["portal_url"] == new_url

    r = client.delete("/api/jobs/acme-1/portal")
    assert r.status_code == 200
    assert r.json()["portal_url"] is None
    assert client.get("/api/jobs/acme-2").json()["portal_url"] is None


def test_rejects_non_http_url():
    _reset()
    _add("acme-1", "Acme Corp")
    r = client.put("/api/jobs/acme-1/portal", json={"portal_url": "ftp://nope"})
    assert r.status_code == 400
