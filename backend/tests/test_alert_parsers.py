"""Deterministic alert-parser tests (Indeed plain text, Glassdoor HTML).

These parsers are the deterministic-first path the ingester prefers over the LLM,
so regressions here silently degrade ingestion quality and salary capture.
"""
from app.services.alert_parsers import (
    extract_salary,
    normalize_location,
    parse_glassdoor,
    parse_indeed,
)


class TestExtractSalary:
    def test_annual_range(self):
        assert extract_salary("Pay: $144K - $288K a year").startswith("$144")

    def test_hourly(self):
        out = extract_salary("Rate is $100/hr depending on experience")
        assert "$100" in out and "/hr" in out

    def test_none_when_absent(self):
        assert extract_salary("No compensation listed here") == ""

    def test_empty_input(self):
        assert extract_salary("") == ""


class TestNormalizeLocation:
    def test_passthrough_city_state(self):
        assert normalize_location("Dallas, TX") == "Dallas, TX"

    def test_strips_whitespace(self):
        assert normalize_location("  Remote  ") == "Remote"

    def test_empty(self):
        assert normalize_location("") == ""


class TestParseIndeed:
    def test_single_job_block(self):
        plain = "\n".join(
            [
                "Senior Software Engineer",
                "Acme Corp - Dallas, TX",
                "$120,000 - $150,000 a year",
                "https://www.indeed.com/rc/clk?jk=abc123def",
            ]
        )
        jobs = parse_indeed(plain)
        assert len(jobs) == 1
        job = jobs[0]
        assert job["title"] == "Senior Software Engineer"
        assert job["company"] == "Acme Corp"
        assert job["location"] == "Dallas, TX"
        assert "indeed.com" in job["url"]
        assert "120,000" in job["salary"]

    def test_no_jobs_without_indeed_url(self):
        plain = "Some Title\nSome Company - Austin, TX\nhttps://example.com/job"
        assert parse_indeed(plain) == []

    def test_empty_input(self):
        assert parse_indeed("") == []


class TestParseGlassdoor:
    def test_single_card(self):
        html = """
        <html><body>
          <a href="https://www.glassdoor.com/partner/jobListing.htm?jobListingId=123">
            <p>Staff Engineer</p>
            <p>Remote</p>
            <span>Globex</span>
          </a>
        </body></html>
        """
        jobs = parse_glassdoor(html)
        assert len(jobs) == 1
        job = jobs[0]
        assert job["title"] == "Staff Engineer"
        assert job["company"] == "Globex"
        assert job["location"] == "Remote"
        assert "jobListing.htm" in job["url"]

    def test_dedups_same_title_company(self):
        card = """
          <a href="https://www.glassdoor.com/partner/jobListing.htm?jobListingId={id}">
            <p>Staff Engineer</p><p>Remote</p><span>Globex</span>
          </a>
        """
        html = f"<html><body>{card.format(id=1)}{card.format(id=2)}</body></html>"
        # Same (title, company) collapses to one row even across two cards.
        assert len(parse_glassdoor(html)) == 1

    def test_ignores_non_job_anchors(self):
        html = '<a href="https://www.glassdoor.com/about">About us</a>'
        assert parse_glassdoor(html) == []
