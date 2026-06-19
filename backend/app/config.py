"""Application configuration.

Everything is overridable via environment variables so the same code runs on a
laptop or a remote server. The DB URL points at the existing jobs.db by default
so we build on the real data instead of starting empty.
"""
from __future__ import annotations

import os
from pathlib import Path

# backend/app/config.py -> repo root is two parents up from this file's parent.
REPO_ROOT = Path(__file__).resolve().parents[2]

# Default to the existing jobs.db that already holds 1,571 real rows.
DEFAULT_DB_PATH = REPO_ROOT / "jobs.db"

DATABASE_URL = os.environ.get(
    "JOBTRACKER_DATABASE_URL",
    f"sqlite:///{DEFAULT_DB_PATH}",
)

# CORS: open by default per the self-hosted "connect from any device" requirement.
# Override with a comma-separated list for a locked-down deployment.
_origins = os.environ.get("JOBTRACKER_CORS_ORIGINS", "*")
CORS_ORIGINS = ["*"] if _origins.strip() == "*" else [
    o.strip() for o in _origins.split(",") if o.strip()
]

# Where uploaded resume PDFs are stored on disk.
RESUME_UPLOAD_DIR = Path(
    os.environ.get("JOBTRACKER_RESUME_DIR", str(REPO_ROOT / "uploads" / "resumes"))
)

# Optional Anthropic key. When absent, the AI compare endpoint returns a
# deterministic heuristic stub so the app is fully functional offline.
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
# Latest, most capable model for the resume-fit analysis when a key is present.
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-8")

# Statuses that make up the visible Kanban pipeline, in display order.
PIPELINE_STATUSES = ["Saved", "Applied", "Interviewing", "Offer", "Rejected", "Expired"]

# How legacy/raw statuses found in the existing data map onto the columns.
# - "Rejected" means the company rejected an application I submitted.
# - "Declined" jobs (I passed on them) are moved to the Skipped bucket via the
#   `ignored` flag, not shown as a pipeline status; if a Skipped/Declined job is
#   restored we surface it under Saved for reconsideration.
# - "Expired" postings lapsed and get their own column.
STATUS_DISPLAY_MAP = {
    "Saved": "Saved",
    "Viewed": "Saved",
    "Applied": "Applied",
    "Interviewing": "Interviewing",
    "Interview": "Interviewing",
    "Offer": "Offer",
    "Rejected": "Rejected",
    "Declined": "Saved",
    "Expired": "Expired",
}
