"""Gemini-backed extraction of jobs from alert emails and resume match scoring.

If GOOGLE_API_KEY is unset or the SDK errors, functions degrade gracefully:
extraction returns [] and scoring returns None, so ingestion still records jobs.
"""
from __future__ import annotations

import json
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


def _gen_json(prompt: str, open_ch: str, close_ch: str):
    client = _get_client()
    if client is None:
        return None
    resp = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
    raw = resp.text or ""
    start, end = raw.find(open_ch), raw.rfind(close_ch)
    if start == -1 or end == -1:
        raise ValueError("no JSON found in model response")
    return json.loads(raw[start : end + 1])


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
