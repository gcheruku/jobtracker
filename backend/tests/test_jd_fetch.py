"""Tests for the pure (no-network) parts of the JD fetcher: link rewriting,
bot-wall / expiry detection, and the HTML->Markdown nested-list handling that
once truncated LinkedIn job descriptions.
"""
from app.services.jd_fetch import (
    _host,
    _indeed_jobview_url,
    _is_expired,
    _linkedin_guest_url,
    _looks_blocked,
    _to_markdown,
)


class TestLinkRewriting:
    def test_linkedin_view_path(self):
        url = "https://www.linkedin.com/comm/jobs/view/3812345678/?trk=eml"
        assert _linkedin_guest_url(url) == "https://www.linkedin.com/jobs/view/3812345678"

    def test_linkedin_current_job_id(self):
        url = "https://www.linkedin.com/jobs/search/?currentJobId=99887766"
        assert _linkedin_guest_url(url) == "https://www.linkedin.com/jobs/view/99887766"

    def test_linkedin_no_id_returns_none(self):
        assert _linkedin_guest_url("https://www.linkedin.com/feed/") is None

    def test_indeed_clk_to_viewjob(self):
        url = "https://www.indeed.com/rc/clk?jk=abc123&from=email"
        assert _indeed_jobview_url(url) == "https://www.indeed.com/viewjob?jk=abc123"

    def test_indeed_no_jk_returns_none(self):
        assert _indeed_jobview_url("https://www.indeed.com/cmp/acme") is None


class TestHostNormalization:
    def test_strips_www(self):
        assert _host("https://www.Indeed.com/viewjob?jk=1") == "indeed.com"

    def test_no_www(self):
        assert _host("https://glassdoor.com/partner") == "glassdoor.com"


class TestBlockDetection:
    def test_cloudflare_challenge_is_blocked(self):
        assert _looks_blocked("<title>Just a moment...</title>") is True

    def test_glassdoor_security_page_is_blocked(self):
        assert _looks_blocked("<title>Security | Glassdoor</title>") is True

    def test_real_posting_not_blocked(self):
        assert _looks_blocked("<h1>Senior Engineer</h1><p>We are hiring</p>") is False


class TestExpiryDetection:
    def test_linkedin_closed_banner(self):
        assert _is_expired("<div>No longer accepting applications</div>") is True

    def test_active_posting(self):
        assert _is_expired("<div>Apply now for this great role</div>") is False


class TestMarkdownNestedLists:
    """Regression: nested LinkedIn bullets used to be dropped entirely."""

    def test_well_formed_nesting(self):
        html = "<ul><li>Parent<ul><li>Child</li></ul></li></ul>"
        md = _to_markdown(html)
        assert "- Parent" in md
        assert "  - Child" in md

    def test_malformed_sibling_nesting(self):
        # LinkedIn emits a sub-<ul> as a sibling of the <li>s, not inside one.
        html = "<ul><li>First</li><ul><li>Nested</li></ul></ul>"
        md = _to_markdown(html)
        assert "- First" in md
        assert "  - Nested" in md

    def test_emphasis_and_headings(self):
        html = "<h2>About</h2><p>We value <strong>ownership</strong>.</p>"
        md = _to_markdown(html)
        assert "## About" in md
        assert "**ownership**" in md
