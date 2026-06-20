"""Turn a raw Gmail job-alert message into a clean payload for the extractor.

We deliberately do NOT hand-write per-provider HTML scrapers (the templates are
image-heavy and change often). Instead we produce: the subject, a plain-text
rendering, and the list of candidate job links (anchor text + href) limited to
the known job domains. The Gemini extractor turns that into structured jobs.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from .gmail_client import header, html_body, internal_epoch

JOB_DOMAINS = ("dice", "indeed", "glassdoor", "linkedin")

# Senders we recognize -> provider name used as the job_key prefix / source.
PROVIDERS = {
    "indeed": "Indeed",
    "glassdoor": "Glassdoor",
    "linkedin": "LinkedIn",
    "dice": "Dice",
}

# Subjects that are alerts but contain no job postings (skip these messages).
_SKIP_SUBJECT_MARKERS = (
    "profile has been viewed",
    "viewed by a recruiter",
    "who viewed your",
    "application was viewed",
)

_SKIP_LINK_MARKERS = (
    "unsubscribe", "privacy", "manage", "settings", "terms", "help",
    "app store", "google play", "premium", "log in", "login", "view all jobs",
    "view community", "knowledge center", "edit this job alert",
)


@dataclass
class EmailPayload:
    message_id: str
    provider: str
    subject: str
    epoch: int
    text: str
    links: List[dict] = field(default_factory=list)


def provider_of(from_header: str) -> str:
    f = from_header.lower()
    for needle, name in PROVIDERS.items():
        if needle in f:
            return name
    return "Email"


def is_job_email(subject: str) -> bool:
    s = subject.lower()
    return not any(marker in s for marker in _SKIP_SUBJECT_MARKERS)


def build_payload(full_msg: dict) -> EmailPayload:
    subject = header(full_msg, "Subject")
    provider = provider_of(header(full_msg, "From"))
    soup = BeautifulSoup(html_body(full_msg["payload"]), "lxml")

    links: List[dict] = []
    seen_urls = set()
    for a in soup.find_all("a", href=True):
        text = a.get_text(" ", strip=True)
        href = a["href"]
        host = urlparse(href).netloc.lower()
        if not any(d in host for d in JOB_DOMAINS):
            continue
        if text and any(m in text.lower() for m in _SKIP_LINK_MARKERS):
            continue
        if href in seen_urls:
            continue
        seen_urls.add(href)
        links.append({"text": text[:90], "url": href})

    return EmailPayload(
        message_id=header(full_msg, "Message-Id") or full_msg.get("id", ""),
        provider=provider,
        subject=subject,
        epoch=internal_epoch(full_msg),
        text=soup.get_text("\n", strip=True)[:6000],
        links=links[:40],
    )
