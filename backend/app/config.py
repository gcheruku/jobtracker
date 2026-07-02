"""Application configuration.

Everything is overridable via environment variables so the same code runs on a
laptop or a remote server. The DB URL points at the existing jobs.db by default
so we build on the real data instead of starting empty.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# backend/app/config.py -> repo root is two parents up from this file's parent.
REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = Path(__file__).resolve().parents[1]

# Load .env files (dotenv strips surrounding quotes, which os.environ would not).
# backend/.env takes precedence over a repo-root .env; in container deploys the
# mounted /data/.env wins (harmless no-op when that path doesn't exist).
load_dotenv(REPO_ROOT / ".env")
load_dotenv(BACKEND_DIR / ".env", override=True)
load_dotenv("/data/.env", override=True)

# Default to the existing jobs.db that already holds 1,571 real rows.
DEFAULT_DB_PATH = REPO_ROOT / "jobs.db"

DATABASE_URL = os.environ.get(
    "JOBTRACKER_DATABASE_URL",
    f"sqlite:///{DEFAULT_DB_PATH}",
)

# CORS: the app is served same-origin — the frontend calls /api through the
# nginx proxy — so cross-origin access isn't needed in normal use. Default to
# localhost dev origins only (no wildcard), which keeps a malicious site in the
# user's browser from reading the API or issuing preflighted writes to a
# LAN/VPN-reachable instance. Set JOBTRACKER_CORS_ORIGINS (comma-separated) to
# add a real origin, or "*" to deliberately open it.
_origins = os.environ.get(
    "JOBTRACKER_CORS_ORIGINS", "http://localhost:5173,http://localhost:8080"
)
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

# --- Gmail ingestion + Gemini scoring -----------------------------------------
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

# Optional OpenAI key for the career assistant (one of the selectable providers).
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o")

# Default agent provider when the user hasn't picked one in Settings.
AGENT_PROVIDER = os.environ.get("AGENT_PROVIDER", "anthropic")

# Gmail OAuth artifacts and the label that holds the job-alert emails.
GMAIL_TOKEN_PATH = Path(
    os.environ.get("GMAIL_TOKEN_PATH", str(BACKEND_DIR / "secrets" / "token.json"))
)
GMAIL_CREDENTIALS_PATH = Path(
    os.environ.get(
        "GMAIL_CREDENTIALS_PATH", str(BACKEND_DIR / "secrets" / "credentials.json")
    )
)
GMAIL_LABEL = os.environ.get("GMAIL_LABEL", "Job alerts")
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

# Resume used for match scoring during ingestion.
RESUME_DOCX_PATH = Path(
    os.environ.get("RESUME_DOCX_PATH", str(REPO_ROOT / "Resume.docx"))
)

# Background fetch cadence and per-run safety cap.
INGEST_INTERVAL_HOURS = float(os.environ.get("INGEST_INTERVAL_HOURS", "4"))
INGEST_MAX_MESSAGES = int(os.environ.get("INGEST_MAX_MESSAGES", "60"))
# Higher cap used for manual "fetch since a date" / "fetch all" runs, which can
# legitimately scan far more of the label than a routine incremental fetch.
INGEST_MAX_MESSAGES_ALL = int(os.environ.get("INGEST_MAX_MESSAGES_ALL", "2000"))
# Run an ingest shortly after startup (in addition to the recurring schedule).
INGEST_RUN_ON_STARTUP = os.environ.get("INGEST_RUN_ON_STARTUP", "false").lower() == "true"

# --- Expired-posting sweep ----------------------------------------------------
# Periodically re-check the Saved column and move lapsed/removed postings to the
# Expired state (see services/expiry.py). Off by default so it's opt-in per
# deployment; the run is network-heavy and hits job boards, so a daily cadence
# at an off-peak hour is the intended setup.
EXPIRY_SWEEP_ENABLED = os.environ.get("EXPIRY_SWEEP_ENABLED", "false").lower() == "true"
EXPIRY_SWEEP_INTERVAL_HOURS = float(os.environ.get("EXPIRY_SWEEP_INTERVAL_HOURS", "24"))
# Seconds paused between per-posting fetches (keeps the host IP off bot-walls).
EXPIRY_SWEEP_DELAY_S = float(os.environ.get("EXPIRY_SWEEP_DELAY_S", "1.0"))

# All valid statuses a job can hold (also the move targets in the drawer).
PIPELINE_STATUSES = ["Saved", "Applied", "Interviewing", "Offer", "Rejected", "Expired"]

# Statuses that appear as columns on the active Kanban board.
BOARD_STATUSES = ["Saved", "Applied", "Interviewing", "Offer"]

# Statuses that are kept off the board and surfaced in the "Inactive" view
# (together with skipped/ignored jobs).
OFF_BOARD_STATUSES = ["Rejected", "Expired"]

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
