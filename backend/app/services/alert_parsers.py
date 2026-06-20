"""Deterministic parsers for Indeed (plain-text) and Glassdoor (HTML) alerts.

Adapted from a proven parser: Indeed alerts carry one job per
"title / company - location / [salary] / <indeed url>" block in the plain-text
part; Glassdoor alerts are HTML cards linking to .../partner/jobListing.htm.
These are more reliable (and capture salary) than LLM extraction for these two
providers. LinkedIn keeps the existing tile/LLM path.
"""
from __future__ import annotations

import re
from typing import List

from bs4 import BeautifulSoup

_nominatim = None


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def normalize_location(location: str) -> str:
    """Clean a location; expand a bare US ZIP to "City, ST" if pgeocode is present."""
    location = (location or "").strip()
    if re.fullmatch(r"\d{5}(-\d{4})?", location):
        try:
            import pgeocode  # optional

            global _nominatim
            if _nominatim is None:
                _nominatim = pgeocode.Nominatim("us")
            rec = _nominatim.query_postal_code(location[:5])
            city, state = rec.get("place_name"), rec.get("state_code")
            if isinstance(city, str) and city:
                return f"{city}, {state}" if isinstance(state, str) and state else city
        except Exception:
            pass
    return location


def _looks_like_location(text: str) -> bool:
    return bool(
        re.search(r",\s*[A-Z]{2}\b", text)
        or re.match(r"(remote|hybrid|united states)", text.strip(), re.I)
        or "remote" in text.lower()
    )


_SALARY_NUM = r"\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?"
_SALARY_PERIOD = (
    r"\s?(?:/\s?|per\s+|a\s+|an\s+)(?:hour|hr|year|yr|annum|annually|day|week|wk|month|mo)"
)
_SALARY_RE = re.compile(
    rf"\$\s?{_SALARY_NUM}\s?[KkMm]?\s?(?:-|–|—|to)\s?\$?\s?{_SALARY_NUM}\s?[KkMm]?(?:{_SALARY_PERIOD})?"
    rf"|\$\s?{_SALARY_NUM}\s?[KkMm]\b(?:{_SALARY_PERIOD})?"
    rf"|\$\s?{_SALARY_NUM}(?:{_SALARY_PERIOD})",
    re.I,
)


def extract_salary(text: str) -> str:
    if not text:
        return ""
    m = _SALARY_RE.search(text)
    return _norm(m.group(0)) if m else ""


_INDEED_JOB_URL = re.compile(r"https?://\S*indeed\.com/(?:rc/clk|pagead|viewjob)", re.I)


def parse_indeed(plain: str) -> List[dict]:
    """Parse Indeed alert plain text into job dicts (title/company/location/url/salary)."""
    lines = [_norm(line) for line in (plain or "").splitlines() if _norm(line)]
    jobs, last_url = [], -1
    for i, line in enumerate(lines):
        if not _INDEED_JOB_URL.match(line):
            continue
        for j in range(i - 1, last_url, -1):
            parts = lines[j].split(" - ", 1)
            if len(parts) == 2 and _looks_like_location(parts[1]) and j - 1 > last_url:
                jobs.append(
                    {
                        "title": lines[j - 1],
                        "company": parts[0].strip(),
                        "location": normalize_location(parts[1].strip()),
                        "url": line,
                        "salary": extract_salary(" ".join(lines[j + 1 : i])),
                    }
                )
                break
        last_url = i
    return jobs


_GLASSDOOR_JOB_HREF = "partner/jobListing.htm"
_GLASSDOOR_RATING = re.compile(r"^\d(?:\.\d)?\s*★")
_GLASSDOOR_TRAILING_RATING = re.compile(r"\s*\d(?:\.\d)?\s*★.*$")


def parse_glassdoor(html: str) -> List[dict]:
    """Parse Glassdoor alert HTML cards into job dicts."""
    soup = BeautifulSoup(html or "", "html.parser")
    jobs, seen = [], set()
    for anchor in soup.find_all("a", href=True):
        if _GLASSDOOR_JOB_HREF not in anchor["href"]:
            continue
        paragraphs = [_norm(p.get_text(" ", strip=True)) for p in anchor.find_all("p")]
        paragraphs = [p for p in paragraphs if p]
        if len(paragraphs) < 2:
            continue
        title = paragraphs[0]
        location = next(
            (p for p in paragraphs[1:] if _looks_like_location(p)), paragraphs[1]
        )
        company = ""
        for span in anchor.find_all("span"):
            if span.find("span"):
                continue
            text = _norm(span.get_text(" ", strip=True))
            if not text or text.startswith("[if") or "<table" in text:
                continue
            if _GLASSDOOR_RATING.match(text):
                continue
            company = _GLASSDOOR_TRAILING_RATING.sub("", text).strip()
            if company:
                break
        if not title or not company:
            continue
        key = (title.lower(), company.lower())
        if key in seen:
            continue
        seen.add(key)
        jobs.append(
            {
                "title": title,
                "company": company,
                "location": normalize_location(location),
                "url": anchor["href"],
                "salary": extract_salary(" ".join(paragraphs)),
            }
        )
    return jobs
