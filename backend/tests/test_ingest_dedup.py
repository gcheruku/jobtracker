"""Tests for the canonical-id extraction and job-key construction that make
incremental ingestion idempotent (resent alerts must not double-insert).
"""
from app.services.ingest import _job_key, _safe, canonical_id


class TestCanonicalId:
    def test_linkedin_view(self):
        assert canonical_id("https://www.linkedin.com/jobs/view/3812345678") == "li-3812345678"

    def test_linkedin_current_job_id(self):
        assert canonical_id("https://www.linkedin.com/jobs/?currentJobId=12345") == "li-12345"

    def test_indeed_jk(self):
        assert canonical_id("https://www.indeed.com/viewjob?jk=abc123def") == "in-abc123def"

    def test_glassdoor_job_listing_id(self):
        url = "https://www.glassdoor.com/partner/jobListing.htm?jobListingId=987654"
        assert canonical_id(url) == "gd-987654"

    def test_unknown_host_returns_none(self):
        assert canonical_id("https://example.com/jobs/123") is None

    def test_none_url(self):
        assert canonical_id(None) is None

    def test_id_is_stable_across_tracking_params(self):
        a = canonical_id("https://www.indeed.com/viewjob?jk=xyz&from=alertA&tk=1")
        b = canonical_id("https://www.indeed.com/rc/clk?jk=xyz&from=alertB&tk=2")
        assert a == b == "in-xyz"


class TestSafe:
    def test_replaces_path_breaking_chars(self):
        assert _safe("a/b\\c") == "a-b-c"


class TestJobKey:
    def test_prefers_canonical_id(self):
        job = {"url": "https://www.indeed.com/viewjob?jk=abc123", "title": "X", "company": "Y"}
        assert _job_key("Indeed", job) == "Indeed:in-abc123"

    def test_falls_back_to_title_company(self):
        job = {"url": None, "title": "Senior Engineer", "company": "Acme"}
        key = _job_key("LinkedIn", job)
        assert key.startswith("LinkedIn:")
        assert "senior engineer" in key.lower()
        assert "acme" in key.lower()
