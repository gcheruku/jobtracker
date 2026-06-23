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
from bs4 import BeautifulSoup, NavigableString, Tag

from ..logging_config import logger

# Indeed (and increasingly Glassdoor) front their pages with Cloudflare, which
# scores a request's TLS/JA3 fingerprint. Plain `requests` has a Python
# fingerprint that Cloudflare flags instantly and answers with a JS "Security
# Check" challenge — so the JD never loads. curl_cffi impersonates a real
# Chrome TLS handshake and sails past that check. Fall back to requests if the
# wheel isn't installed (the app still works for non-protected sites).
try:
    from curl_cffi import requests as _cffi  # type: ignore

    _IMPERSONATE = "chrome"
except Exception:  # pragma: no cover - optional dependency
    _cffi = None
    _IMPERSONATE = None


def _http_get(url: str, timeout: int):
    """GET a URL with a browser-grade TLS fingerprint when curl_cffi is present,
    otherwise plain requests. Returns the response (status_code/text/url)."""
    headers = {"User-Agent": _UA, "Accept-Language": "en-US,en;q=0.9"}
    if _cffi is not None:
        return _cffi.get(
            url,
            impersonate=_IMPERSONATE,
            headers={"Accept-Language": "en-US,en;q=0.9"},
            timeout=timeout,
            allow_redirects=True,
        )
    return requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)

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

# Inline tags whose children should flow together without surrounding newlines.
_INLINE = {"strong", "b", "em", "i", "u", "span", "a", "code", "small"}


def _md_inline(node) -> str:
    """Convert an inline node (or string) to Markdown, preserving emphasis/links."""
    if isinstance(node, NavigableString):
        return re.sub(r"[ \t\r\n]+", " ", str(node))
    if not isinstance(node, Tag):
        return ""
    name = (node.name or "").lower()
    inner = "".join(_md_inline(c) for c in node.children)
    if name in ("strong", "b"):
        return f"**{inner.strip()}**" if inner.strip() else ""
    if name in ("em", "i"):
        return f"*{inner.strip()}*" if inner.strip() else ""
    if name == "a":
        href = (node.get("href") or "").strip()
        text = inner.strip()
        return f"[{text}]({href})" if href and text else text
    if name == "br":
        return "  \n"
    return inner


def _md_list(node, lines: list[str], depth: int) -> None:
    """Render a <ul>/<ol> to indented Markdown list items, recursing into nested
    lists. Handles both well-formed nesting (a sub-list inside an <li>) and the
    malformed shape LinkedIn emits (a sub-<ul> as a direct sibling of <li>s) —
    the old direct-<li>-only walk dropped every nested bullet."""
    name = (node.name or "").lower()
    indent = "  " * depth
    n = 0
    for child in node.children:
        if not isinstance(child, Tag):
            continue
        cname = (child.name or "").lower()
        if cname == "li":
            # Split the item's own text from any lists nested within it.
            inline_parts, sublists = [], []
            for c in child.children:
                if isinstance(c, Tag) and (c.name or "").lower() in ("ul", "ol"):
                    sublists.append(c)
                else:
                    inline_parts.append(_md_inline(c))
            n += 1
            bullet = f"{n}." if name == "ol" else "-"
            text = "".join(inline_parts).strip()
            if text:
                lines.append(f"{indent}{bullet} {text}")
            for sl in sublists:
                _md_list(sl, lines, depth + 1)
        elif cname in ("ul", "ol"):
            # Malformed: a nested list sitting directly under this one.
            _md_list(child, lines, depth + 1)


def _md_block(node, lines: list[str]) -> None:
    """Walk block-level nodes, appending Markdown blocks/list items to `lines`."""
    if isinstance(node, NavigableString):
        text = re.sub(r"[ \t\r\n]+", " ", str(node)).strip()
        if text:
            lines.append(text)
        return
    if not isinstance(node, Tag):
        return
    name = (node.name or "").lower()
    if name in ("script", "style"):
        return
    if name in ("ul", "ol"):
        _md_list(node, lines, 0)
        lines.append("")
        return
    if re.fullmatch(r"h[1-6]", name):
        level = min(int(name[1]), 4)
        lines.append(f"{'#' * level} {_md_inline(node).strip()}")
        lines.append("")
        return
    if name in ("p", "div", "section", "article", "li"):
        # Block container: if it holds block children, recurse; else emit inline.
        if any(isinstance(c, Tag) and (c.name or "").lower() not in _INLINE | {"br"} for c in node.children):
            for c in node.children:
                _md_block(c, lines)
        else:
            text = _md_inline(node).strip()
            if text:
                lines.append(text)
                lines.append("")
        return
    # Inline or unknown wrapper: flatten to inline text.
    text = _md_inline(node).strip()
    if text:
        lines.append(text)


def _to_markdown(html: str) -> str:
    """Best-effort HTML -> Markdown that keeps headings, lists, emphasis, links."""
    soup = BeautifulSoup(html or "", "lxml")
    root = soup.body or soup
    lines: list[str] = []
    for child in root.children:
        _md_block(child, lines)
    md = "\n".join(lines)
    md = re.sub(r"\n{3,}", "\n\n", md).strip()
    return md


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
                md = _to_markdown(obj.get("description", "") or "")
                if len(md) >= _MIN_CHARS:
                    return md
    # 2) Known content containers.
    for sel in _SELECTORS:
        el = soup.select_one(sel)
        if el:
            md = _to_markdown(str(el))
            if len(md) >= _MIN_CHARS:
                return md
    return ""


def _linkedin_guest_url(url: str) -> str | None:
    m = re.search(r"/jobs/view/(\d+)", url) or re.search(r"currentJobId=(\d+)", url)
    return f"https://www.linkedin.com/jobs/view/{m.group(1)}" if m else None


def _indeed_jobview_url(url: str) -> str | None:
    """Rewrite an Indeed alert/apply link (/rc/clk, /pagead, ...) to the canonical
    viewjob page. The original links redirect straight to the employer's ATS
    (often a JS-only SPA with no extractable JD), whereas viewjob serves a clean
    JSON-LD JobPosting. Keyed on the `jk` job id present in most Indeed links."""
    m = re.search(r"[?&]jk=([0-9a-f]+)", url, re.I) or re.search(r"/viewjob/([0-9a-f]+)", url, re.I)
    return f"https://www.indeed.com/viewjob?jk={m.group(1)}" if m else None


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
    low = url.lower()
    if "linkedin" in low:
        guest = _linkedin_guest_url(url)
        if guest:
            targets.append(guest)
    if "indeed." in low:
        viewjob = _indeed_jobview_url(url)
        if viewjob and viewjob != url:
            targets.append(viewjob)
    targets.append(url)  # also try the original link as a fallback

    for target in targets:
        try:
            resp = _http_get(target, timeout)
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
