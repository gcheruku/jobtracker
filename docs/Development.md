# Local Development

How to run JobTrack on a laptop. The app is designed to run with **no keys at
all** (with reduced features), so you can get a UI up in two terminals before
configuring anything.

> See also: [Architecture.md](Architecture.md), [Deployment.md](Deployment.md).

---

## 1. Prerequisites

- **Python 3.11+**
- **Node 18+**
- (Optional) A Google **Gemini API key** (AI compare + ingestion scoring), an
  **Anthropic** or **OpenAI** key (the agent), and **Gmail OAuth** credentials
  (email ingestion).

---

## 2. Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # then edit (see §4)
uvicorn app.main:app --port 8000   # no --reload (in-process scheduler)
```

On first run the app **creates a fresh `jobs.db`** automatically. Interactive API
docs are at <http://localhost:8000/docs>.

> Run without `--reload`: the app starts an in-process APScheduler, and the
> reloader would spawn a second scheduler.

### Optional: offline semantic matching

```bash
pip install -r requirements-semantic.txt   # adds sentence-transformers / Torch
```

This is heavy (PyTorch). It is optional everywhere; the app degrades to "no
semantic scoring" when absent.

---

## 3. Frontend

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173 (proxies /api -> :8000)
```

| Script | Purpose |
|---|---|
| `npm run dev` | Vite dev server with HMR + `/api` proxy |
| `npm run build` | Type-check (`tsc -b`) then production build to `dist/` |
| `npm run preview` | Serve the production build locally |

Production / remote build:

```bash
cd frontend && VITE_API_BASE=http://YOUR_SERVER:8000 npm run build
# serve frontend/dist statically (nginx, python -m http.server, or FastAPI StaticFiles)
```

---

## 4. Configuration

All config is environment-driven (see [`backend/.env.example`](../backend/.env.example)
and [`backend/app/config.py`](../backend/app/config.py)). Everything is optional —
the app runs without any of it, with reduced features.

| Variable | Default | Effect |
|---|---|---|
| `GOOGLE_API_KEY` | — | Enables Gemini AI compare + ingestion extraction/scoring |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Gemini model id |
| `ANTHROPIC_API_KEY` | — | Enables the Claude agent / resume analysis |
| `ANTHROPIC_MODEL` | `claude-opus-4-8` | Claude model id |
| `OPENAI_API_KEY` | — | Enables OpenAI as an agent provider |
| `OPENAI_MODEL` | `gpt-4o` | OpenAI model id |
| `AGENT_PROVIDER` | `anthropic` | Default agent provider when unset in Settings |
| `RESUME_DOCX_PATH` | `../Resume.docx` | Resume `.docx` used for match scoring (supply your own) |
| `JOBTRACKER_DATABASE_URL` | `sqlite:///jobs.db` | DB URL (point at Postgres if desired) |
| `JOBTRACKER_CORS_ORIGINS` | localhost dev origins | Comma-separated origins, or `*` to open |
| `GMAIL_LABEL` | `Job alerts` | Gmail label that holds the alert emails |
| `GMAIL_CREDENTIALS_PATH` / `GMAIL_TOKEN_PATH` | `backend/secrets/*` | Gmail OAuth files |
| `INGEST_INTERVAL_HOURS` | `4` | Background ingest cadence |
| `INGEST_MAX_MESSAGES` | `60` | Per-run safety cap on emails |

### Gmail ingestion (optional)

Follow [`backend/secrets/README.md`](../backend/secrets/README.md) to create an
OAuth desktop client, enable the Gmail API, and generate `token.json` with the
read-only scope. Route your Dice/LinkedIn/Glassdoor/Indeed alerts to the
`Job alerts` label. `reauth_gmail.py` regenerates the token if its refresh token
is revoked.

---

## 5. Project conventions

- **Routers stay thin.** Validation + wiring only; business logic lives in
  `services/`. The scheduler and the agent call services directly.
- **Config is centralized** in `app/config.py` — read env vars there, not
  scattered through modules.
- **Graceful degradation is a contract.** A missing key disables a feature with a
  clear message; it never crashes a request path.

---

## 6. Testing

A starter test suite lives in [`backend/tests/`](../backend/tests/) and covers
the deterministic core: alert parsing, JD link rewriting + bot-wall/expiry
detection + the HTML→Markdown nested-list handling, canonical-id dedup,
preference matching, and the agent tool-surface contract. The tests are pure
(no network, no real DB).

```bash
cd backend
pip install -r requirements-dev.txt
python -m pytest
```

Config is in [`backend/pytest.ini`](../backend/pytest.ini). See
[TECHNICAL_DEBT.md](../TECHNICAL_DEBT.md) for the coverage still to add (route
tests, provider-adapter contract tests, CI gating).

## 7. Troubleshooting

| Symptom | Likely cause |
|---|---|
| Two ingests run per interval | Started uvicorn with `--reload` (spawns a second scheduler). Drop `--reload`. |
| JD fetch returns a "Security Check" page | Anti-bot wall; the host may be in cooldown or the NAS IP block-listed. See [Architecture §5.2](Architecture.md). |
| "Compare with Resume" gives a heuristic result | No `GOOGLE_API_KEY` / `ANTHROPIC_API_KEY`; the app fell back to the offline heuristic. |
| Assistant panel shows a "no key" banner | The selected agent provider has no key; pick another provider in Settings or set its key. |
| Gmail ingestion disabled | No `secrets/credentials.json` + `token.json`; see `backend/secrets/README.md`. |
