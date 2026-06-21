# JobTrack — Self-Hosted Job Tracking Dashboard

A self-hosted job tracker with a **FastAPI + SQLite** backend and a
**Vite + React + TypeScript + Tailwind** frontend. It ingests job-alert emails
from Gmail, scores them against your resume, and gives you a Kanban board,
filtering, preferences, and an AI resume-fit analysis.

> No personal data is in this repo — your resume, Gmail credentials, `.env`, and
> the SQLite database are all gitignored. Sample/template files are provided so
> you can supply your own.

## Features
- **Kanban board** (Saved / Applied / Interviewing / Offer) with drag-and-drop.
- **Gmail ingestion** of Dice/LinkedIn/Glassdoor/Indeed alerts — scheduled every
  4h and via a manual **Fetch alerts** button; deduped by posting id.
- **Offline semantic match** (sentence-transformers) of your resume vs each job.
- **AI "Compare with Resume"** — detailed Gemini analysis (match score, skill
  gaps, red flags, improvements).
- **Preferences** (salary / location+distance / min score / keywords) that move
  non-matching jobs to a **Mismatched** view; skipped/expired/rejected go to
  **Inactive**.
- **Global search**, job drawer with notes & checklists, expiry detection.

## Setup

### Prerequisites
- Python 3.11+ and Node 18+
- (Optional) A Google **Gemini API key** for the AI compare, and Gmail OAuth
  credentials for ingestion.

### 1. Backend
```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # then edit (see below)
uvicorn app.main:app --port 8000   # no --reload (in-process scheduler)
```
On first run the app **creates a fresh `jobs.db`** automatically. API docs at
http://localhost:8000/docs.

Edit `.env` (all optional — the app runs without them, with reduced features):
- `GOOGLE_API_KEY` — enables Gemini "Compare with Resume".
- `RESUME_DOCX_PATH` — path to your resume `.docx` (default `../Resume.docx`),
  used for match scoring. Provide your own; it is **not** in the repo.
- Gmail ingestion: put OAuth files in `backend/secrets/` — see
  [`backend/secrets/README.md`](backend/secrets/README.md).
- See [`backend/.env.example`](backend/.env.example) for the full list.

### 2. Frontend
```bash
cd frontend
npm install
npm run dev          # http://localhost:5173 (proxies /api -> :8000)
```

### Production / remote
```bash
cd frontend && VITE_API_BASE=http://YOUR_SERVER:8000 npm run build
# serve frontend/dist statically (nginx, python -m http.server, or FastAPI StaticFiles)
```
CORS is open by default (`JOBTRACKER_CORS_ORIGINS` to restrict).

## Project layout
```
jobtracker/
├── backend/          FastAPI app (app/), requirements.txt, .env.example, secrets/
├── frontend/         Vite + React app (src/components, src/lib)
├── prompts/          The prompts used to build this + the figma design
└── README.md
```

## Notes
- The startup migration is additive and idempotent (`ALTER TABLE ADD COLUMN` +
  `create_all`) — it never drops or rewrites rows, so it safely upgrades an
  existing `jobs.db` or bootstraps a new one.
- Without a Gemini key, "Compare with Resume" falls back to an offline heuristic;
  without Gmail credentials, ingestion is disabled but everything else works.
