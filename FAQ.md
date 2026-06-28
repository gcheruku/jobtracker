# FAQ

### What is JobTrack?

A self-hosted, single-user job-search tracker. It ingests job-alert emails from
Gmail, fetches and scores each posting against your résumé, and tracks it through
a Kanban pipeline — with a tool-using AI assistant on top. See the
[README](README.md).

### Do I need API keys to run it?

No. The app runs with **no keys** (with reduced features): you get the board,
search, preferences, manual entry, and an offline keyword-overlap résumé
heuristic. Adding a Gemini/Anthropic/OpenAI key unlocks LLM scoring and the AI
assistant; Gmail OAuth unlocks email ingestion.

### Which LLM providers are supported?

Three, and the AI assistant is selectable between them in Settings:
**Anthropic (Claude)**, **Google Gemini**, and **OpenAI**. Only the *selected*
provider needs a key. Résumé-fit "Compare with Resume" uses Gemini (or the
offline heuristic).

### Is any of my personal data in this repository?

No. Your résumé, `.env`, Gmail credentials/token, and the SQLite database are all
gitignored. Only example/template files are committed. See [SECURITY.md](SECURITY.md).

### How does it fetch job descriptions if job boards block scrapers?

Per-site. Cloudflare scores the TLS fingerprint, so the fetcher uses a
browser-impersonating client (`curl_cffi`) for Indeed/LinkedIn and plain
`requests` for Glassdoor (which blocks the impersonated fingerprint), rewrites
tracking links to canonical URLs, and applies a host-scoped cooldown after a
challenge page. Details in [docs/Architecture.md](docs/Architecture.md#52-job-description-fetching-servicesjd_fetchpy).

### Why an agent instead of a single LLM prompt?

The questions are open-ended and need live, per-user data — the model must decide
which jobs to inspect, read their details, and compare them to the résumé. That
requires tool use and a loop, not one call. See [docs/AI-Agent.md](docs/AI-Agent.md).

### Can the AI assistant change my data?

Not in v1 — all agent tools are read-only, and the loop is capped at 8 steps.
Write tools (behind an approval queue) are on the [roadmap](ROADMAP.md).

### Why SQLite instead of Postgres?

It's a single-user, file-backed, zero-ops fit. The database URL is configurable,
so pointing at Postgres is a config change, not a rewrite.

### Why run it on a NAS with a self-hosted runner instead of the cloud?

To get push-to-deploy with **no public attack surface and no cloud bill**. The
NAS only makes outbound calls; remote access is via Tailscale. See
[docs/Deployment.md](docs/Deployment.md).

### How do I deploy my own copy?

Follow [docs/Deployment.md](docs/Deployment.md). If you fork it for real use,
keep the repo **private** — the deploy runner mounts `docker.sock`.
