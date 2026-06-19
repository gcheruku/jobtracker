"""Resume-vs-job fit analysis.

Two modes:
  * heuristic-stub (default): keyword overlap scoring + templated prep questions
    and tips. Fully deterministic, no network, works offline. This is the "stub
    out the LLM payload" the spec asks for.
  * llm: if ANTHROPIC_API_KEY is set and the anthropic SDK is installed, we call
    Claude (claude-opus-4-8 by default) and parse a structured JSON response.

The function signature and return shape are identical for both, so the frontend
never needs to know which path produced the result.
"""
from __future__ import annotations

import json
import re
from typing import List

from ..config import ANTHROPIC_API_KEY, ANTHROPIC_MODEL
from ..schemas import CompareResult, KeywordChip

# A compact skills vocabulary used to extract candidate keywords from free text.
# Kept intentionally broad; the heuristic is a stand-in for a real LLM extractor.
_SKILL_VOCAB = [
    "python", "java", "javascript", "typescript", "go", "golang", "rust", "c++",
    "react", "vue", "angular", "node", "fastapi", "django", "flask", "spring",
    "sql", "postgres", "postgresql", "mysql", "sqlite", "mongodb", "redis",
    "aws", "gcp", "azure", "kubernetes", "docker", "terraform", "ci/cd",
    "graphql", "rest", "microservices", "distributed systems", "kafka",
    "machine learning", "ml", "ai", "llm", "nlp", "pytorch", "tensorflow",
    "data", "etl", "spark", "airflow", "analytics", "leadership", "mentoring",
    "agile", "scrum", "system design", "scalability", "security", "testing",
    "observability", "grafana", "prometheus", "linux", "git", "api",
]

_STOPWORDS = {"and", "the", "with", "for", "you", "our", "are", "will"}


def _extract_keywords(text: str) -> set[str]:
    if not text:
        return set()
    lowered = text.lower()
    found = {kw for kw in _SKILL_VOCAB if kw in lowered}
    # Also pull capitalized/tech-looking single tokens not already covered.
    for token in re.findall(r"[a-zA-Z][a-zA-Z0-9+#.]{2,}", lowered):
        if token in _SKILL_VOCAB and token not in _STOPWORDS:
            found.add(token)
    return found


def _heuristic(job_key: str, job_text: str, resume_text: str) -> CompareResult:
    job_kw = _extract_keywords(job_text)
    resume_kw = _extract_keywords(resume_text)

    if not job_kw:
        # Nothing to match against — be honest rather than fabricating a score.
        return CompareResult(
            job_key=job_key,
            match_score=0,
            matched_keywords=[],
            missing_keywords=[],
            keyword_chips=[],
            interview_questions=[
                "Walk me through a project you're most proud of.",
                "Why are you interested in this role?",
            ],
            resume_tips=[
                "Add a job description for this role to get a real keyword match.",
            ],
            summary="No job description text was available to analyze.",
            source="heuristic-stub",
        )

    matched = sorted(job_kw & resume_kw)
    missing = sorted(job_kw - resume_kw)
    score = round(100 * len(matched) / max(1, len(job_kw)))

    chips: List[KeywordChip] = (
        [KeywordChip(label=k, matched=True) for k in matched]
        + [KeywordChip(label=k, matched=False) for k in missing]
    )

    questions = [
        f"Can you describe your hands-on experience with {kw}?"
        for kw in (matched[:3] or missing[:3])
    ] or ["Tell me about a recent technical challenge you solved."]
    questions.append("How would you approach the first 90 days in this role?")

    tips = []
    if missing:
        tips.append(
            "Surface these missing keywords if you have the experience: "
            + ", ".join(missing[:6]) + "."
        )
    tips.append("Quantify impact (latency, scale, revenue) on your top bullets.")
    tips.append("Mirror the job's exact title and core stack in your summary line.")

    summary = (
        f"You match {len(matched)} of {len(job_kw)} key skills "
        f"({score}%). Strongest overlaps: {', '.join(matched[:4]) or 'none yet'}."
    )

    return CompareResult(
        job_key=job_key,
        match_score=score,
        matched_keywords=matched,
        missing_keywords=missing,
        keyword_chips=chips,
        interview_questions=questions,
        resume_tips=tips,
        summary=summary,
        source="heuristic-stub",
    )


def _llm(job_key: str, job_text: str, resume_text: str) -> CompareResult:
    """Call Claude for a richer analysis. Falls back to heuristic on any error."""
    try:
        from anthropic import Anthropic

        client = Anthropic(api_key=ANTHROPIC_API_KEY)
        prompt = (
            "You are a technical recruiter. Compare the RESUME to the JOB and "
            "return ONLY minified JSON with keys: match_score (int 0-100), "
            "matched_keywords (string[]), missing_keywords (string[]), "
            "interview_questions (string[]), resume_tips (string[]), "
            "summary (string).\n\n"
            f"JOB:\n{job_text[:6000]}\n\nRESUME:\n{resume_text[:6000]}"
        )
        msg = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = "".join(
            block.text for block in msg.content if getattr(block, "type", "") == "text"
        )
        data = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
        matched = data.get("matched_keywords", [])
        missing = data.get("missing_keywords", [])
        return CompareResult(
            job_key=job_key,
            match_score=int(data.get("match_score", 0)),
            matched_keywords=matched,
            missing_keywords=missing,
            keyword_chips=(
                [KeywordChip(label=k, matched=True) for k in matched]
                + [KeywordChip(label=k, matched=False) for k in missing]
            ),
            interview_questions=data.get("interview_questions", []),
            resume_tips=data.get("resume_tips", []),
            summary=data.get("summary", ""),
            source="llm",
        )
    except Exception:
        # Never fail the request because the LLM is unavailable.
        return _heuristic(job_key, job_text, resume_text)


def compare_resume_to_job(job_key: str, job_text: str, resume_text: str) -> CompareResult:
    if ANTHROPIC_API_KEY:
        return _llm(job_key, job_text, resume_text)
    return _heuristic(job_key, job_text, resume_text)
