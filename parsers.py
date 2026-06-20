"""Parse and clean job postings from raw email alerts.

This module turns a job-alert email body into a list of structured job
dictionaries. It also handles light data cleaning such as collapsing
whitespace and normalising US ZIP codes into "City, ST" locations.

LinkedIn and Indeed alerts are parsed from their plain-text part:
    LinkedIn:  title / company / location / "View job: <url>"
    Indeed:    title / "company - location" / [salary] / [desc] / [date] / <url>
Glassdoor alerts are HTML-only, so they are parsed from the HTML instead
(each job is an <a href=".../partner/jobListing.htm"> card).
"""
import json
import re

import pgeocode
from bs4 import BeautifulSoup

# Lazily-initialised geocoder; building it is relatively expensive.
_nominatim = None


def _norm(text):
    """Collapse runs of whitespace and strip the ends of a string."""
    return re.sub(r"\s+", " ", text or "").strip()


def normalize_location(location):
    """Clean a location string, expanding a bare US ZIP code to "City, ST".

    Args:
        location: Raw location text from an email.

    Returns:
        A cleaned location string. ZIP codes that cannot be resolved are
        returned unchanged.
    """
    location = location.strip()
    if re.fullmatch(r"\d{5}(-\d{4})?", location):
        global _nominatim
        if _nominatim is None:
            _nominatim = pgeocode.Nominatim("us")
        record = _nominatim.query_postal_code(location[:5])
        city, state = record.get("place_name"), record.get("state_code")
        if isinstance(city, str) and city:
            if isinstance(state, str) and state:
                return f"{city}, {state}"
            return city
    return location


def _looks_like_location(text):
    """Heuristic: does ``text`` resemble a US location or remote/hybrid tag?"""
    return bool(
        re.search(r",\s*[A-Z]{2}\b", text)
        or re.match(r"(remote|hybrid|united states)", text.strip(), re.I)
        or "remote" in text.lower()
    )


# A salary figure ($1,234, $99,000.00, $75K), optionally a range and a pay
# period. To avoid false positives (e.g. "$50 gift card") a match must look
# like pay: a range, a K/M magnitude, or an explicit period.
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


def extract_salary(text):
    """Return a salary range/figure found in ``text``, or "" if none.

    Recognises common alert and description formats such as
    "$225,000 - $250,000 a year", "$75K - $85K", "$60.00 - $75.00 per hour"
    and "$140,000/year". Returns the first salary-like match, whitespace
    normalised.
    """
    if not text:
        return ""
    match = _SALARY_RE.search(text)
    return _norm(match.group(0)) if match else ""


# Social-proof / status lines LinkedIn sometimes inserts between the location
# and the "View job:" line (e.g. "2 connections", "46 company alumni",
# "This company is actively hiring", "1 school alum"). These must be skipped,
# otherwise they shift the title/company/location fields off the posting.
_LINKEDIN_NOISE = re.compile(
    r"^(?:"
    r"[\d,]+\s+(?:connection|connections|applicant|applicants"
    r"|(?:school |company )?alum(?:ni)?)"
    r"|this company is actively hiring"
    r"|actively (?:hiring|recruiting)"
    r"|easy apply|promoted|be an early applicant"
    r"|viewed|saved"
    r")\b",
    re.I,
)


def parse_linkedin(plain):
    """Parse LinkedIn job-alert plain text into a list of job dicts.

    Each job has ``title``, ``company``, ``location`` and ``url`` keys.

    The three content lines (title, company, location) appear immediately
    above the "View job:" link, but LinkedIn occasionally inserts a
    social-proof line such as "2 connections" between the location and the
    link. Those noise lines are skipped so the fields stay aligned.
    """
    lines = [_norm(line) for line in plain.splitlines() if _norm(line)]
    jobs = []
    for i, line in enumerate(lines):
        match = re.match(r"View job:\s*(\S+)", line)
        if not match:
            continue
        # Walk upward, skipping noise, to collect location, company, title.
        content = []
        j = i - 1
        while j >= 0 and len(content) < 3:
            if not _LINKEDIN_NOISE.match(lines[j]):
                content.append(lines[j])
            j -= 1
        if len(content) == 3:
            location, company, title = content
            jobs.append(
                {
                    "title": title,
                    "company": company,
                    "location": normalize_location(location),
                    "url": match.group(1),
                    # LinkedIn alerts rarely carry pay; it is filled from the
                    # description during scoring when available.
                    "salary": extract_salary(" ".join(content)),
                }
            )
    return jobs


_INDEED_JOB_URL = re.compile(r"https?://\S*indeed\.com/(?:rc/clk|pagead|viewjob)", re.I)


def parse_indeed(plain):
    """Parse Indeed job-alert plain text into a list of job dicts.

    Each job has ``title``, ``company``, ``location`` and ``url`` keys.
    """
    lines = [_norm(line) for line in plain.splitlines() if _norm(line)]
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
                        # Pay (if present) sits in the lines between the
                        # company/location line and the job URL.
                        "salary": extract_salary(" ".join(lines[j + 1:i])),
                    }
                )
                break
        last_url = i
    return jobs


# A Glassdoor job card links to the partner redirect; inside it the company
# sits next to its "X.X ★" rating, then the title/location/salary in <p> tags.
_GLASSDOOR_JOB_HREF = "partner/jobListing.htm"
_GLASSDOOR_RATING = re.compile(r"^\d(?:\.\d)?\s*★")
_GLASSDOOR_TRAILING_RATING = re.compile(r"\s*\d(?:\.\d)?\s*★.*$")


def parse_glassdoor(html):
    """Parse Glassdoor job-alert HTML into a list of job dicts.

    Each job is an ``<a href=".../partner/jobListing.htm...">`` card whose
    company appears in a leaf ``<span>`` (next to a "X.X ★" rating span) and
    whose title and location are the first ``<p>`` tags. Cards are de-duplicated
    within the email by (title, company).

    Args:
        html: The HTML body of a Glassdoor alert email.

    Returns:
        A list of dicts with ``title``, ``company``, ``location`` and ``url``.
    """
    soup = BeautifulSoup(html, "html.parser")
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
                continue  # only leaf spans hold the individual fields
            text = _norm(span.get_text(" ", strip=True))
            if not text or text.startswith("[if") or "<table" in text:
                continue
            if _GLASSDOOR_RATING.match(text):
                continue  # the rating span
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
                # One of the <p> tags holds the pay range, e.g. "$75K - $85K".
                "salary": extract_salary(" ".join(paragraphs)),
            }
        )
    return jobs


def detect_source(sender):
    """Return "LinkedIn", "Indeed", "Glassdoor", or None from the email sender."""
    sender = sender.lower()
    if "linkedin" in sender:
        return "LinkedIn"
    if "indeed" in sender:
        return "Indeed"
    if "glassdoor" in sender:
        return "Glassdoor"
    return None


def detect_source_from_url(url):
    """Return "LinkedIn"/"Indeed"/"Glassdoor" from a job URL's domain, or None."""
    low = (url or "").lower()
    if "linkedin.com" in low:
        return "LinkedIn"
    if "indeed.com" in low:
        return "Indeed"
    if "glassdoor." in low:
        return "Glassdoor"
    return None


def _first_text(soup, *selectors):
    """Return the text of the first matching CSS selector, or ""."""
    for selector in selectors:
        element = soup.select_one(selector)
        if element:
            text = _norm(element.get_text(" ", strip=True))
            if text:
                return text
    return ""


def parse_posting_page(source, html):
    """Extract a single posting's fields from its job page HTML.

    Returns a dict with ``title``, ``company``, ``location``, ``salary`` and
    ``description`` (any of which may be ""). Tuned for LinkedIn's guest job
    view; other sources fall back to Open Graph / page heuristics.
    """
    soup = BeautifulSoup(html or "", "html.parser")
    if source == "LinkedIn":
        return _parse_linkedin_page(soup)
    return _parse_generic_page(soup)


def _parse_linkedin_page(soup):
    """Extract fields from a LinkedIn guest job-view page."""
    title = _first_text(soup, "h1.top-card-layout__title", "h1")
    company = _first_text(soup, "a.topcard__org-name-link", ".topcard__org-name-link")
    location = ""
    for element in soup.select(".topcard__flavor--bullet"):
        text = _norm(element.get_text(" ", strip=True))
        if text and _looks_like_location(text):
            location = text
            break
    markup = soup.select_one("div.show-more-less-html__markup")
    description = _norm(markup.get_text(" ", strip=True)) if markup else ""
    salary = extract_salary(description) or extract_salary(soup.get_text(" ", strip=True))
    return {
        "title": title,
        "company": company,
        "location": normalize_location(location),
        "salary": salary,
        "description": description,
    }


def _find_jobposting_ld(soup):
    """Return the schema.org JobPosting dict from a page's JSON-LD, or None.

    Most applicant-tracking and career sites embed a ``JobPosting`` block in a
    ``<script type="application/ld+json">`` tag, which carries the fields far
    more reliably than scraping the rendered markup.
    """
    for block in soup.find_all("script", {"type": "application/ld+json"}):
        if not block.string:
            continue
        try:
            data = json.loads(block.string)
        except (json.JSONDecodeError, TypeError):
            continue
        for item in data if isinstance(data, list) else [data]:
            if isinstance(item, dict) and item.get("@type") == "JobPosting":
                return item
    return None


def _ld_location(posting):
    """Build a "City, ST" string from a JobPosting's jobLocation, or ""."""
    location = posting.get("jobLocation")
    if isinstance(location, list):
        location = location[0] if location else None
    if not isinstance(location, dict):
        return ""
    address = location.get("address")
    if not isinstance(address, dict):
        return ""
    city = _norm(address.get("addressLocality", ""))
    region = _norm(address.get("addressRegion", ""))
    return ", ".join(part for part in (city, region) if part)


def _ld_salary(posting):
    """Format a JobPosting's baseSalary as a salary string, or ""."""
    base = posting.get("baseSalary")
    if not isinstance(base, dict):
        return ""
    value = base.get("value")
    if not isinstance(value, dict):
        return ""
    unit = (value.get("unitText") or "").title()
    low, high = value.get("minValue"), value.get("maxValue")
    amount = value.get("value")
    def money(num):
        try:
            return f"${float(num):,.0f}"
        except (TypeError, ValueError):
            return ""
    if low and high:
        figure = f"{money(low)} - {money(high)}"
    elif amount:
        figure = money(amount)
    else:
        return ""
    return _norm(f"{figure}{' / ' + unit if unit else ''}")


def _parse_generic_page(soup):
    """Best-effort field extraction for a non-LinkedIn job page.

    Prefers a schema.org JobPosting (JSON-LD) when present -- that gives a full
    title, company, location, salary and description -- and otherwise falls back
    to Open Graph tags and page heuristics.
    """
    def og(prop):
        tag = soup.find("meta", {"property": prop})
        return _norm(tag["content"]) if tag and tag.get("content") else ""

    page_text = soup.get_text(" ", strip=True)
    posting = _find_jobposting_ld(soup)
    if posting:
        org = posting.get("hiringOrganization")
        company = _norm(org.get("name", "")) if isinstance(org, dict) else ""
        description = _norm(
            BeautifulSoup(posting.get("description", ""), "html.parser").get_text(
                " ", strip=True
            )
        )
        return {
            "title": _norm(posting.get("title", "")) or og("og:title"),
            "company": company,
            "location": normalize_location(_ld_location(posting)),
            "salary": _ld_salary(posting)
            or extract_salary(description)
            or extract_salary(page_text),
            "description": description or og("og:description"),
        }

    description = og("og:description")
    return {
        "title": og("og:title") or _first_text(soup, "h1", "title"),
        "company": "",
        "location": "",
        "salary": extract_salary(description) or extract_salary(page_text),
        "description": description,
    }


def parse_jobs(source, body):
    """Dispatch to the correct parser for a given source.

    Args:
        source: "LinkedIn", "Indeed" or "Glassdoor".
        body: The email body -- plain text for LinkedIn/Indeed, HTML for
            Glassdoor.

    Returns:
        A list of job dicts, or an empty list for unknown sources.
    """
    if source == "LinkedIn":
        return parse_linkedin(body)
    if source == "Indeed":
        return parse_indeed(body)
    if source == "Glassdoor":
        return parse_glassdoor(body)
    return []


def job_key(source, url, title, company):
    """Build a stable identity for a job so duplicates merge across runs.

    Uses the platform's job ID when present in the URL, otherwise falls
    back to a normalised title/company pair.
    """
    if source == "LinkedIn":
        match = re.search(r"/jobs/view/(\d+)", url)
    else:
        match = re.search(r"[?&]jk=([0-9A-Za-z]+)", url)
    identity = match.group(1) if match else f"{title}|{company}".lower()
    return f"{source}:{identity}"
