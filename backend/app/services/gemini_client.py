"""Gemini-backed extraction of jobs from alert emails and resume match scoring.

If GOOGLE_API_KEY is unset or the SDK errors, functions degrade gracefully:
extraction returns [] and scoring returns None, so ingestion still records jobs.
"""
from __future__ import annotations

import json
import re
from typing import List, Optional

from ..config import GEMINI_MODEL, GOOGLE_API_KEY
from ..logging_config import logger
from .email_parser import EmailPayload

_client = None


def _get_client():
    global _client
    if not GOOGLE_API_KEY:
        return None
    if _client is None:
        from google import genai

        _client = genai.Client(api_key=GOOGLE_API_KEY)
    return _client


def _gen_json(prompt: str, open_ch: str, close_ch: str, model: str | None = None):
    client = _get_client()
    if client is None:
        return None
    resp = client.models.generate_content(model=model or GEMINI_MODEL, contents=prompt)
    raw = resp.text or ""
    start, end = raw.find(open_ch), raw.rfind(close_ch)
    if start == -1 or end == -1:
        raise ValueError("no JSON found in model response")
    return json.loads(raw[start : end + 1])


def list_models() -> list[str]:
    """Available Gemini models that support content generation."""
    client = _get_client()
    if client is None:
        return []
    try:
        out = []
        for m in client.models.list():
            name = (m.name or "").replace("models/", "")
            actions = getattr(m, "supported_actions", None) or getattr(
                m, "supported_generation_methods", None
            ) or []
            if "gemini" in name and (not actions or "generateContent" in actions):
                out.append(name)
        # Stable, useful-first ordering.
        preferred = [
            "gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.0-flash",
            "gemini-1.5-pro", "gemini-1.5-flash",
        ]
        ranked = [m for m in preferred if m in out] + sorted(
            m for m in out if m not in preferred
        )
        return ranked
    except Exception as exc:
        logger.warning("Could not list Gemini models: %s", exc)
        return []


# Prompt for the detailed "Compare with Resume" analysis. Produces a rich
# Markdown report (rendered in the UI) prefixed with a parseable SCORE line.
_FIT_PROMPT = """You are an expert technical recruiter and an advanced Applicant \
Tracking System (ATS). Analyze the following Resume against the Job Description. \
Be specific and evidence-based: cite actual phrases from the resume and the job \
description. Do NOT invent experience the resume does not show.

Scoring guidance: score primarily on whether the candidate CAN do the job — \
coverage of the required skills and whether their experience depth meets or \
exceeds the requirements. A candidate who clearly meets or exceeds the core \
requirements should score 80-95. Treat over-qualification, short tenures, minor \
keyword gaps, or location as MINOR deductions (a few points each), not major \
penalties. Reserve scores below 50 for candidates genuinely lacking the core \
required skills or experience.

First, output a single line exactly in this format (nothing before it):
SCORE: <integer 0-100>

Then provide a detailed analysis in GitHub-flavored Markdown with these sections:

## 1. Contextual Match Score
State the score as a percentage and justify it in a short paragraph based on \
skills, experience depth, and seniority alignment.

## 2. Keyword & Skills Alignment
What matches (cite specific resume phrases and the JD requirements they satisfy) \
and what critical/required skills are missing or flagged.

## 3. Experience & Red Flags Gap Analysis
Analyze whether the depth and seniority of experience truly fit. Call out red \
flags (over- or under-qualification, short tenures, domain switch, location \
mismatch, missing required keywords).

## 4. Actionable Bullet Point Improvements
Rewrite 2-3 existing resume bullet points to mirror key verbs/metrics from the \
JD WITHOUT fabricating data. Show the **Original** and the **Improved** version.

[JOB DESCRIPTION]
{job}

[RESUME]
{resume}
"""

_SCORE_RE = re.compile(r"SCORE:\s*(\d{1,3})", re.IGNORECASE)


def analyze_fit(job_text: str, resume_text: str, model: str | None = None) -> Optional[dict]:
    """Markdown resume-vs-job fit analysis via Gemini. None if unavailable."""
    if _get_client() is None or not resume_text:
        return None
    client = _get_client()
    prompt = _FIT_PROMPT.format(job=job_text[:12000], resume=resume_text[:9000])
    resp = client.models.generate_content(model=model or GEMINI_MODEL, contents=prompt)
    raw = (resp.text or "").strip()
    if not raw:
        return None

    m = _SCORE_RE.search(raw)
    score = int(m.group(1)) if m else 0
    # Drop the SCORE: line and any stray code-fence wrapper from the markdown.
    md = _SCORE_RE.sub("", raw, count=1)
    md = re.sub(r"^```(?:markdown)?\s*|\s*```$", "", md.strip()).strip()
    return {"match_score": max(0, min(100, score)), "report_markdown": md}


def extract_jobs(payload: EmailPayload) -> List[dict]:
    """Return a list of {title, company, location, url, salary} from one email."""
    if _get_client() is None:
        return []
    prompt = (
        "Extract DISTINCT real job postings from this job-alert email. "
        "Return ONLY a minified JSON array; each item has keys "
        '"title","company","location","url","salary". '
        "Pick the url ONLY from the provided LINKS list (match by title); if no "
        'matching link, use "". Skip ads, recruiter messages, and non-jobs. '
        'Use "" for unknown fields.\n\n'
        f"SUBJECT: {payload.subject}\n\n"
        f"LINKS: {json.dumps(payload.links)}\n\n"
        f"TEXT:\n{payload.text}"
    )
    try:
        data = _gen_json(prompt, "[", "]")
        return data if isinstance(data, list) else []
    except Exception as exc:
        logger.warning("Gemini extraction failed for '%s': %s", payload.subject[:40], exc)
        return []


def parse_tiles(tiles: List[dict]) -> List[dict]:
    """Parse each job tile's text into structured fields, keeping its own URL.

    `tiles` is [{url, text}] where each text is the DOM block for ONE job, so the
    parsed title/company/location/salary and the URL all come from the same
    listing — no cross-job misassignment. Non-job tiles are dropped by the model.
    """
    if _get_client() is None or not tiles:
        return []
    items = [{"i": i, "text": t["text"]} for i, t in enumerate(tiles)]
    prompt = (
        "Each item below is the text of ONE job listing from an alert email. "
        "For each REAL job, return an object "
        '{"i":int,"title","company","location","salary"} parsed from that item\'s '
        "text, keeping the same i. Omit items that are not real postings (saved-"
        'search headers, "see more", ads). Use "" for unknown fields. '
        "Return ONLY a minified JSON array.\n\n" + json.dumps(items)
    )
    try:
        data = _gen_json(prompt, "[", "]")
        out: List[dict] = []
        for d in data or []:
            i = d.get("i")
            if isinstance(i, int) and 0 <= i < len(tiles) and d.get("title"):
                d["url"] = tiles[i]["url"]
                out.append(d)
        return out
    except Exception as exc:
        logger.warning("Gemini tile parse failed: %s", exc)
        return []


def score_job(job: dict, resume: str) -> Optional[dict]:
    """Return {match:int, matched:[], missing:[], summary:str} or None."""
    if _get_client() is None or not resume:
        return None
    job_text = json.dumps(
        {k: job.get(k, "") for k in ("title", "company", "location", "salary")}
    )
    prompt = (
        "Score how well this RESUME fits the JOB on a 0-100 scale. "
        "Return ONLY minified JSON with keys "
        '"match" (int), "matched" (string[]), "missing" (string[]), '
        '"summary" (one sentence).\n\n'
        f"JOB: {job_text}\n\nRESUME:\n{resume[:6000]}"
    )
    try:
        data = _gen_json(prompt, "{", "}")
        if data is not None:
            data["match"] = int(data.get("match", 0))
        return data
    except Exception as exc:
        logger.warning("Gemini scoring failed for '%s': %s", job.get("title", "")[:40], exc)
        return None
