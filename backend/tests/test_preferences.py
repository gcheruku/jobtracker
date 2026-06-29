"""Tests for preference matching: salary annualization, home-state parsing, and
the lenient `job_matches` rules (unknown data never disqualifies a job).

`job_matches` only touches the DB session for the distance branch, which is
skipped when `Settings.city` is empty — so these tests pass `session=None`.
"""
from app.models import Job
from app.schemas import Settings
from app.services.preferences import (
    _geo_query,
    _home_state,
    job_matches,
    parse_salary_annual,
)


def _job(**kw) -> Job:
    kw.setdefault("job_key", "test:1")
    return Job(**kw)


class TestParseSalaryAnnual:
    def test_k_range(self):
        assert parse_salary_annual("$144K - $288K") == (144000, 288000)

    def test_hourly_annualized(self):
        assert parse_salary_annual("$100/hr") == (208000, 208000)

    def test_daily_annualized(self):
        assert parse_salary_annual("$950 a day") == (247000, 247000)

    def test_unparseable(self):
        assert parse_salary_annual("competitive") is None

    def test_none(self):
        assert parse_salary_annual(None) is None


class TestHomeStateAndGeoQuery:
    def test_home_state_extracted(self):
        assert _home_state("Irving, TX") == "TX"

    def test_home_state_absent(self):
        assert _home_state("Remote") == ""

    def test_geo_query_biases_to_home_state(self):
        assert _geo_query("Frisco", "TX") == "Frisco, TX"

    def test_geo_query_keeps_existing_state(self):
        assert _geo_query("Dallas, TX", "TX") == "Dallas, TX"


class TestJobMatches:
    def test_salary_below_minimum_is_mismatch(self):
        job = _job(salary="$120,000 - $150,000 a year")
        ok, reason = job_matches(None, job, Settings(salary_min=200000), None)
        assert ok is False
        assert "salary below" in reason

    def test_salary_within_range_matches(self):
        job = _job(salary="$120,000 - $150,000 a year")
        ok, _ = job_matches(None, job, Settings(salary_min=100000), None)
        assert ok is True

    def test_unknown_salary_is_lenient(self):
        # No salary on the job: a salary preference must not disqualify it.
        job = _job(salary=None)
        ok, _ = job_matches(None, job, Settings(salary_min=200000), None)
        assert ok is True

    def test_title_keyword_required(self):
        job = _job(title="Senior Engineer")
        assert job_matches(None, job, Settings(title_keywords=["manager"]), None)[0] is False
        assert job_matches(None, job, Settings(title_keywords=["engineer"]), None)[0] is True

    def test_excluded_company(self):
        job = _job(company="Acme Corp")
        ok, reason = job_matches(None, job, Settings(exclude_companies=["acme"]), None)
        assert ok is False
        assert "excluded company" in reason

    def test_min_match_score(self):
        assert job_matches(None, _job(compare_score=50), Settings(min_match_score=80), None)[0] is False
        assert job_matches(None, _job(compare_score=90), Settings(min_match_score=80), None)[0] is True
