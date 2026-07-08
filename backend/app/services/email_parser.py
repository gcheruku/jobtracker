"""Turn a raw Gmail job-alert message into a clean payload for the extractor.

We deliberately do NOT hand-write per-provider HTML scrapers. Instead, for every
job-domain link we capture its *tile text* — the text of the smallest DOM block
that wraps exactly that one job (which contains the title/company/location). The
Gemini extractor parses the email into structured jobs, and each job's URL is
then matched to the link whose tile text contains its title+company. This pairs
URLs by content, never by order, so links can't be shifted/misassigned.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional
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
    "unsubscribe", "privacy policy", "manage settings", "see all jobs",
    "see more jobs", "view all jobs", "view community", "knowledge center",
    "edit this job alert", "create job alert", "app store", "google play",
    "try premium",
)

# Longest a single job tile's text should be; bounds how far we climb the DOM.
_TILE_MAX_CHARS = 320


@dataclass
class EmailPayload:
    message_id: str
    provider: str
    subject: str
    epoch: int
    text: str
    links: List[dict] = field(default_factory=list)  # {url, text(tile)}


def norm(s: Optional[str]) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def _is_job_anchor(href: str) -> bool:
    host = urlparse(href).netloc.lower()
    return any(d in host for d in JOB_DOMAINS)


# Href patterns that identify an actual job-posting link (vs. saved-search
# headers, "see more jobs", company pages, or other nav).
_POSTING_PATTERNS = (
    "joblisting",      # Glassdoor
    "/jobs/view",      # LinkedIn
    "/rc/clk", "/viewjob", "jk=", "/pagead/clk",  # Indeed
    "dice.com/job", "/job-detail", "/jobs/detail",  # Dice (direct links)
    # Dice alert emails wrap every job in an opaque click-tracker
    # (e.g. elinks.dice.com/a/sc/<token>/<token>/22) with no decodable target
    # URL. We accept these as posting candidates and rely on the tile-text skip
    # markers + the LLM tile extractor to drop nav links (unsubscribe, "see all
    # jobs", etc.), exactly as we already do for other providers.
    "dice.com/a/sc/",  # Dice email click-tracker
)


def _is_job_posting(href: str) -> bool:
    if not _is_job_anchor(href):
        return False
    h = href.lower()
    return any(p in h for p in _POSTING_PATTERNS)


def _tile_text(anchor) -> str:
    """Text of the smallest ancestor block that wraps exactly this one job link.

    Climbs parents while the subtree still contains a single job link and stays
    within a size bound, so the result holds this job's title/company but does
    not bleed into neighboring tiles.
    """
    chosen = ""
    node = anchor
    while node.parent is not None:
        parent = node.parent
        job_links = sum(
            1 for a in parent.find_all("a", href=True) if _is_job_anchor(a["href"])
        )
        if job_links > 1:
            break
        chosen = parent.get_text(" ", strip=True)
        if len(chosen) > _TILE_MAX_CHARS:
            break
        node = parent
    return chosen[:_TILE_MAX_CHARS]


def match_tile(title: str, company: str, links: List[dict]) -> Optional[str]:
    """Return the URL whose tile text best matches this job's title (+company).

    Matching is purely by content: the correct tile contains the job's title, so
    we never rely on the order links appear in the email.
    """
    nt, nc = norm(title), norm(company)
    if not nt:
        return None
    t_tokens = set(nt.split())
    best_url, best_score = None, 0.0
    for link in links:
        lt = norm(link.get("text"))
        if not lt:
            continue
        title_hit = nt in lt
        overlap = len(t_tokens & set(lt.split())) / max(1, len(t_tokens))
        if not title_hit and overlap < 0.8:
            continue
        score = (2.0 if title_hit else 0.0) + overlap + (0.6 if nc and nc in lt else 0.0)
        if score > best_score:
            best_score, best_url = score, link["url"]
    return best_url


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
        href = a["href"]
        if not _is_job_posting(href) or href in seen_urls:
            continue
        tile = _tile_text(a)
        low = tile.lower()
        if not tile or any(m in low for m in _SKIP_LINK_MARKERS):
            continue
        seen_urls.add(href)
        links.append({"text": tile, "url": href})

    return EmailPayload(
        message_id=header(full_msg, "Message-Id") or full_msg.get("id", ""),
        provider=provider,
        subject=subject,
        epoch=internal_epoch(full_msg),
        text=soup.get_text("\n", strip=True)[:6000],
        links=links[:60],
    )
