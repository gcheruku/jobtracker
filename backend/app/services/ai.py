"""Resume-vs-job fit analysis for the 'Compare with Resume' feature.

Primary path is Gemini (services.gemini_client.analyze_fit), which returns a rich
Markdown report plus a parsed score. Falls back to a small Markdown heuristic when
no Google API key is configured.
"""
from __future__ import annotations

from ..config import GEMINI_MODEL, GOOGLE_API_KEY
from ..logging_config import logger
from .gemini_client import analyze_fit

_SKILL_VOCAB = [
    "python", "java", "javascript", "typescript", "go", "rust", "c++", "react",
    "vue", "angular", "node", "fastapi", "django", "spring", "sql", "postgres",
    "mysql", "mongodb", "redis", "aws", "gcp", "azure", "kubernetes", "docker",
    "terraform", "graphql", "rest", "microservices", "kafka", "machine learning",
    "ml", "ai", "llm", "leadership", "agile", "system design", "security",
]


def _keywords(text: str) -> set[str]:
    low = (text or "").lower()
    return {kw for kw in _SKILL_VOCAB if kw in low}


def _heuristic_fit(job_text: str, resume_text: str) -> dict:
    job_kw = _keywords(job_text)
    matched = sorted(job_kw & _keywords(resume_text))
    missing = sorted(job_kw - _keywords(resume_text))
    score = round(100 * len(matched) / max(1, len(job_kw))) if job_kw else 0
    md = (
        "## 1. Contextual Match Score\n"
        f"**{score}%** — keyword-based estimate (offline heuristic). Set a Google "
        "API key for a full contextual ATS analysis.\n\n"
        "## 2. Keyword & Skills Alignment\n"
        f"**Matches:** {', '.join(matched) or 'none detected'}\n\n"
        f"**Missing:** {', '.join(missing[:10]) or 'none detected'}\n\n"
        "## 3. Experience & Red Flags Gap Analysis\n"
        "Heuristic mode does not assess seniority or domain depth.\n\n"
        "## 4. Actionable Bullet Point Improvements\n"
        "- Surface the missing skills above if you have that experience.\n"
        "- Quantify impact (scale, latency, revenue) on your strongest bullets.\n"
    )
    return {
        "match_score": score,
        "report_markdown": md,
        "model": "heuristic",
        "source": "heuristic-stub",
    }


def compute_fit(job_text: str, resume_text: str, model: str | None = None) -> dict:
    """Return {match_score, report_markdown, model, source}.

    When a Gemini key is configured, a failure RAISES (so the caller can report
    it and the user can retry) rather than silently caching a heuristic result.
    The heuristic is only used when genuinely offline (no key).
    """
    if GOOGLE_API_KEY:
        data = analyze_fit(job_text, resume_text, model=model)  # may raise
        if not data or not data.get("report_markdown"):
            raise RuntimeError("Gemini returned an empty analysis")
        data["source"] = "gemini"
        data["model"] = model or GEMINI_MODEL
        return data
    logger.info("No GOOGLE_API_KEY — using offline heuristic for compare")
    return _heuristic_fit(job_text, resume_text)
