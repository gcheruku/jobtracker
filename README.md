# JobTrack — Self-Hosted Job Tracking Dashboard

Decoupled architecture: a **Python/FastAPI** backend over **SQLite** (SQLModel) and a
**Vite + React + TypeScript + Tailwind** frontend. Builds directly on the existing
`jobs.db` (your real ingested job data) — no data is dropped or recreated.

## File structure

```
jobtracker/
├── jobs.db                     # existing SQLite DB (1,571 real rows) — used as-is
├── jobs.db.backup-*            # timestamped backup made before first run
├── backend/
│   ├── requirements.txt
│   ├── .env.example
│   └── app/
│       ├── main.py             # FastAPI app + CORS + startup migration
│       ├── config.py           # env-driven settings, pipeline + status maps
│       ├── database.py         # engine + non-destructive ADD COLUMN / create_all
│       ├── models.py           # Job (existing table) + Note/Resume/ChecklistItem
│       ├── schemas.py          # request/response models
│       ├── routers/
│       │   ├── jobs.py         # CRUD, status move, ignore/restore, notes, checklist
│       │   ├── resume.py       # paste text / upload PDF, activate, delete
│       │   ├── ai.py           # POST /api/ai/compare/{job_key}
│       │   └── stats.py        # metric cards + recent activity
│       └── services/ai.py      # heuristic stub + optional Claude (claude-opus-4-8)
└── frontend/
    ├── package.json
    ├── vite.config.ts          # dev proxy /api -> :8000
    └── src/
        ├── App.tsx             # layout, optimistic Kanban moves
        ├── lib/{api,types,ui}.ts
        └── components/         # Sidebar, TopBar, MetricCards, KanbanBoard,
                                # JobDrawer, ComparePanel, ActivityLog, IgnoredView
```

## Data model notes

- The existing `jobs` table is reused. The app only **adds** two nullable columns on
  first run: `ignored` (boolean) and `work_mode`. `note`, `resume`, and
  `checklist_item` are new tables created alongside.
- **Pipeline columns:** Saved · Applied · Interviewing · Offer · Rejected. Legacy
  statuses map for display (`Viewed→Saved`, `Declined/Expired→Rejected`); the original
  value is preserved in the DB and returned as `raw_status`.
- **Ignore:** a job can be ignored (hidden from the board, kept in the DB) and later
  restored to its prior status or deleted — see the **Ignored** view.

## Run it

### 1. Backend (port 8000)
```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
Interactive API docs: http://localhost:8000/docs

### 2. Frontend (port 5173)
```bash
cd frontend
npm install
npm run dev        # open http://localhost:5173
```
`vite.config.ts` proxies `/api` → `http://localhost:8000`, so no CORS setup is needed
in dev.

### Production / remote
```bash
cd frontend && VITE_API_BASE=http://YOUR_SERVER:8000 npm run build
# serve frontend/dist as static files (nginx, `python -m http.server`, or FastAPI StaticFiles)
```
The backend enables open CORS by default so any device on your network can connect.

## AI Resume Fit

`POST /api/ai/compare/{job_key}` compares the active resume against a job and returns a
match score, matched/missing keyword chips, interview prep questions, and resume tips.

- **Offline default:** a deterministic keyword-overlap heuristic (`source: heuristic-stub`).
- **Real LLM:** set `ANTHROPIC_API_KEY` (and optionally `ANTHROPIC_MODEL`, default
  `claude-opus-4-8`) to get Claude-generated analysis. Falls back to the heuristic on any
  error, so the endpoint never hard-fails.

Add a resume first via the API (`POST /api/resumes/text` or `/api/resumes/upload`).

## Safety

A timestamped copy of `jobs.db` is created before the first run. The startup migration
is idempotent and only uses additive `ALTER TABLE ADD COLUMN` + `create_all` — it never
drops or rewrites existing rows.
