"""Adding a job from a career-portal URL.

Covers the deterministic JSON-LD extraction, the fetch_job_posting wrapper, and
the POST /api/jobs/from-url endpoint (network + LLM stubbed).
"""
import json

from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, select

from app.database import engine
from app.main import app
from app.models import Job
from app.services import jd_fetch
from app.services.jd_fetch import JobPosting, _extract, _extract_meta, fetch_job_posting

_DESC = "We are hiring a Senior Backend Engineer. " * 12  # > 200 chars

_JSONLD_HTML = f"""
<html><head>
<script type="application/ld+json">
{json.dumps({
    "@type": "JobPosting",
    "title": "Senior Backend Engineer",
    "hiringOrganization": {"@type": "Organization", "name": "Globex"},
    "jobLocation": {"@type": "Place", "address": {
        "@type": "PostalAddress", "addressLocality": "Austin", "addressRegion": "TX"}},
    "baseSalary": {"@type": "MonetaryAmount", "currency": "USD", "value": {
        "@type": "QuantitativeValue", "minValue": 150000, "maxValue": 190000,
        "unitText": "YEAR"}},
    "description": f"<p>{_DESC}</p>",
})}
</script></head><body><h1>Senior Backend Engineer</h1></body></html>
"""


class TestExtractMeta:
    def test_reads_jsonld_fields(self):
        meta = _extract_meta(_JSONLD_HTML)
        assert meta["title"] == "Senior Backend Engineer"
        assert meta["company"] == "Globex"
        assert meta["location"] == "Austin, TX"
        assert meta["salary"] == "$150,000 - $190,000/yr"

    def test_title_falls_back_to_page_title(self):
        html = "<html><head><title>Staff SRE - Initech</title></head><body></body></html>"
        assert _extract_meta(html)["title"] == "Staff SRE - Initech"


# A Next.js career SPA (e.g. Walmart) with the job in a __NEXT_DATA__ blob and
# no JSON-LD — the initial HTML renders client-side.
_NEXT_HTML = f"""
<html><head><title>Staff SRE</title>
<script id="__NEXT_DATA__" type="application/json">
{json.dumps({"props": {"pageProps": {"jobDetails": {
    "title": "Staff Site Reliability Engineer",
    "brand": "Vizio",
    "primaryLocation": {"city": "DALLAS", "stateCode": "TX"},
    "payRange": [{"min": "150000", "max": "200000"}],
    "payFrequency": "Annual",
    "description": "<h2>What you'll do</h2><p>" + ("Keep systems reliable. " * 20) + "</p>",
}}}})}
</script></head><body><div id="root">Loading…</div></body></html>
"""


class TestEmbeddedJson:
    def test_extract_meta_from_next_data(self):
        meta = _extract_meta(_NEXT_HTML)
        assert meta["title"] == "Staff Site Reliability Engineer"
        assert meta["company"] == "Vizio"
        assert meta["location"] == "Dallas, TX"
        assert meta["salary"] == "$150,000 - $200,000/yr"

    def test_extract_description_from_next_data(self):
        md = _extract(_NEXT_HTML)
        assert "What you'll do" in md
        assert len(md) >= 200

    def test_fetch_job_posting_via_next_data(self, monkeypatch):
        monkeypatch.setattr(
            jd_fetch, "_http_get",
            lambda *a, **k: SimpleNamespace(status_code=200, text=_NEXT_HTML),
        )
        p = fetch_job_posting("https://careers.example.com/us/en/jobs/R-1")
        assert p.title == "Staff Site Reliability Engineer"
        assert p.company == "Vizio"
        assert p.location == "Dallas, TX"
        assert p.salary == "$150,000 - $200,000/yr"
        assert len(p.description) >= 200


def test_fetch_job_posting_parses_page(monkeypatch):
    monkeypatch.setattr(
        jd_fetch, "_http_get", lambda *a, **k: SimpleNamespace(status_code=200, text=_JSONLD_HTML)
    )
    p = fetch_job_posting("https://careers.globex.com/jobs/123")
    assert p.title == "Senior Backend Engineer"
    assert p.company == "Globex"
    assert p.location == "Austin, TX"
    assert len(p.description) >= 200
    assert p.not_found is False


def _client_with_clean_db() -> TestClient:
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        for j in s.exec(select(Job)).all():
            s.delete(j)
        s.commit()
    return TestClient(app)


class TestFromUrlEndpoint:
    def test_creates_job_from_posting(self, monkeypatch):
        monkeypatch.setattr(
            "app.routers.jobs.fetch_job_posting",
            lambda url: JobPosting(_DESC, "Senior Backend Engineer", "Globex",
                                   "Austin, TX", "$150,000 - $190,000/yr", False, False),
        )
        c = _client_with_clean_db()
        r = c.post("/api/jobs/from-url", json={"url": "https://careers.globex.com/jobs/123"})
        assert r.status_code == 201, r.text
        job = r.json()
        assert job["title"] == "Senior Backend Engineer"
        assert job["company"] == "Globex"
        assert job["source"] == "Manual"
        assert job["status"] == "Saved"
        assert (job["job_description"] or "").startswith("We are hiring")

    def test_idempotent_same_url_returns_existing(self, monkeypatch):
        monkeypatch.setattr(
            "app.routers.jobs.fetch_job_posting",
            lambda url: JobPosting(_DESC, "Role", "Acme", "", "", False, False),
        )
        c = _client_with_clean_db()
        u = "https://careers.acme.com/jobs/9"
        first = c.post("/api/jobs/from-url", json={"url": u}).json()
        second = c.post("/api/jobs/from-url", json={"url": u}).json()
        assert first["job_key"] == second["job_key"]
        with Session(engine) as s:
            assert len([j for j in s.exec(select(Job)).all() if j.url == u]) == 1

    def test_rejects_non_http_url(self):
        c = _client_with_clean_db()
        r = c.post("/api/jobs/from-url", json={"url": "ftp://nope"})
        assert r.status_code == 400

    def test_404_posting_is_rejected(self, monkeypatch):
        monkeypatch.setattr(
            "app.routers.jobs.fetch_job_posting",
            lambda url: JobPosting("", "", "", "", "", False, True),
        )
        c = _client_with_clean_db()
        r = c.post("/api/jobs/from-url", json={"url": "https://x.com/gone"})
        assert r.status_code == 422

    def test_unreadable_posting_is_rejected(self, monkeypatch):
        # No structured fields, no description -> nothing to extract.
        monkeypatch.setattr(
            "app.routers.jobs.fetch_job_posting",
            lambda url: JobPosting("", "", "", "", "", False, False),
        )
        c = _client_with_clean_db()
        r = c.post("/api/jobs/from-url", json={"url": "https://x.com/login-wall"})
        assert r.status_code == 422
