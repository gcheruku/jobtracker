"""Best-effort job-description fetcher.

Email-alert links are tracking redirects that often hit a login wall. Where
possible we rewrite to a public page (notably LinkedIn's guest job view) and
pull the JD from JSON-LD JobPosting or known content selectors. Returns "" when
nothing usable is found (LinkedIn usually works; Indeed/Glassdoor vary).
"""
from __future__ import annotations

import json
import re

import requests
from bs4 import BeautifulSoup

from ..logging_config import logger

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/123.0 Safari/537.36"
)
_SELECTORS = [
    ".show-more-less-html__markup",        # LinkedIn guest
    ".description__text",
    "#jobDescriptionText",                  # Indeed
    ".jobDescriptionContent",               # Glassdoor (classic)
    "[data-test=jobDescription]",
    "[class*=jobDescription]",              # Glassdoor React SPA (JobDetails_jobDescription__…)
    "[class*=JobDescription]",
    "[class*=description__]",
]
_MIN_CHARS = 200


def _extract(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    # 1) Structured data: JSON-LD JobPosting.description (richest, cleanest).
    for sc in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(sc.string or "{}")
        except Exception:
            continue
        for obj in data if isinstance(data, list) else [data]:
            if isinstance(obj, dict) and "JobPosting" in str(obj.get("@type", "")):
                desc = BeautifulSoup(obj.get("description", "") or "", "lxml").get_text(
                    " ", strip=True
                )
                if len(desc) >= _MIN_CHARS:
                    return desc
    # 2) Known content containers.
    for sel in _SELECTORS:
        el = soup.select_one(sel)
        if el:
            text = el.get_text(" ", strip=True)
            if len(text) >= _MIN_CHARS:
                return text
    return ""


def _linkedin_guest_url(url: str) -> str | None:
    m = re.search(r"/jobs/view/(\d+)", url) or re.search(r"currentJobId=(\d+)", url)
    return f"https://www.linkedin.com/jobs/view/{m.group(1)}" if m else None


# Phrases that appear near the top of an expired/closed posting.
_EXPIRY_MARKERS = (
    "no longer accepting applications",       # LinkedIn
    "job expired", "this job has expired", "this job is expired",  # Glassdoor/Indeed
    "this job has been removed", "no longer available",
    "applications are no longer being accepted", "posting has expired",
    "this position has been filled", "no longer active",
)


def _is_expired(html: str) -> bool:
    """True if an expiry banner appears near the top of the page."""
    soup = BeautifulSoup(html, "lxml")
    top = soup.get_text(" ", strip=True)[:4000].lower()
    return any(marker in top for marker in _EXPIRY_MARKERS)


def fetch_jd_and_expiry(url: str | None, timeout: int = 25) -> tuple[str, bool]:
    """Return (job_description, expired). expired=True if the posting page shows
    an expiry/closed banner near the top."""
    if not url:
        return "", False
    targets: list[str] = []
    if "linkedin" in url.lower():
        guest = _linkedin_guest_url(url)
        if guest:
            targets.append(guest)
    targets.append(url)  # also try the original link as a fallback

    for target in targets:
        try:
            resp = requests.get(
                target,
                headers={"User-Agent": _UA, "Accept-Language": "en-US,en;q=0.9"},
                timeout=timeout,
                allow_redirects=True,
            )
            if resp.status_code >= 400:
                continue
            expired = _is_expired(resp.text)
            desc = _extract(resp.text)
            if desc:
                logger.info("Fetched JD (%d chars) from %s", len(desc), target[:60])
            if desc or expired:
                return desc, expired
        except Exception as exc:
            logger.warning("JD fetch failed for %s: %s", target[:60], exc)
    return "", False


def fetch_job_description(url: str | None, timeout: int = 25) -> str:
    return fetch_jd_and_expiry(url, timeout)[0]
