# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project aims
to follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Public-portfolio documentation set: `docs/Architecture.md`, `docs/AI-Agent.md`,
  `docs/Deployment.md`, `docs/Development.md`, plus Mermaid diagrams.
- GitHub project files: `LICENSE`, `CONTRIBUTING.md`, `SECURITY.md`,
  `CODE_OF_CONDUCT.md`, `ROADMAP.md`, `FAQ.md`, issue/PR templates.
- `TECHNICAL_DEBT.md` and `PORTFOLIO_REVIEW.md`.
- Starter backend test suite (`backend/tests/`, pytest) covering alert parsing,
  JD link rewriting / bot-wall / Markdown handling, canonical-id dedup,
  preference matching, and the agent tool-surface contract.
- CI workflow (`.github/workflows/ci.yml`) running backend `pytest` and frontend
  `tsc -b && vite build` on every PR and on pushes to main.

### Changed
- Rewrote `README.md` for a public audience (features, architecture, "Why I
  built this").
- Consolidated deployment docs under `docs/`.

## [0.4.0] — Semantic scoring by default

### Added
- Semantic resume↔JD matching by default via Gemini embeddings (no Torch
  required), with sorting and a Saved-only backfill.

## [0.3.0] — Provider-selectable AI assistant

### Added
- Career assistant: a tool-using agent over the pipeline (Anthropic / Gemini /
  OpenAI), streamed over SSE; provider selectable in Settings.

## [0.2.0] — Ingestion hardening & performance

### Added
- Per-host bot-wall cooldown so a blocked NAS IP isn't re-flagged.
- `ACCESS_TOKEN`-based self-hosted runner documentation; surfaced fetch-start
  errors.

### Changed
- Locked down CORS (was `*`) to localhost dev origins.
- Cut initial JS bundle ~50% via vendor splitting, lazy Markdown rendering, and
  immutable asset caching.

### Fixed
- Glassdoor JD fetch broken by the `curl_cffi` switch (per-host client order).
- "Skip" in focus view now advances to the next job instead of exiting.

## [0.1.0] — Initial application

### Added
- FastAPI + SQLite backend; Vite + React + Tailwind frontend.
- Gmail job-alert ingestion (Dice/LinkedIn/Glassdoor/Indeed), dedup, JD fetch.
- Kanban board, preferences, resume-fit "Compare with Resume" analysis.
- Self-hosted Synology deployment via a GitHub Actions runner.

[Unreleased]: https://github.com/gcheruku/jobtracker/commits/main
