# Contributing

Thanks for your interest in JobTrack. This is primarily a personal/portfolio
project, but issues and pull requests are welcome.

## Getting set up

See [docs/Development.md](docs/Development.md) for local setup. The app runs with
no API keys (reduced features), so you can get a UI up quickly.

## Ground rules

- **Keep routers thin.** Validation and wiring belong in `routers/`; business
  logic belongs in `services/`. The scheduler and the agent call services
  directly, so logic must live there to stay reusable.
- **Centralize config.** Read environment variables in `backend/app/config.py`,
  not scattered through modules.
- **Preserve graceful degradation.** A missing key disables a feature with a
  clear message — it must never crash a request path.
- **No secrets, ever.** Never commit `.env`, `jobs.db`, OAuth tokens, or a real
  résumé. See [SECURITY.md](SECURITY.md) and the `.gitignore`.

## Workflow

1. Fork and create a feature branch (`feat/...`, `fix/...`, `docs/...`).
2. Make focused changes; match the style and comment density of the surrounding
   code.
3. Verify locally:
   - Backend: `python -m pytest` passes; `uvicorn app.main:app --port 8000`
     starts cleanly and `/docs` loads. Add tests for new deterministic logic.
   - Frontend: `npm run build` type-checks and builds.
4. Open a pull request using the template; describe the change and how you
   tested it.

## Commit messages

Use clear, imperative subjects (e.g. "Add per-host fetch cooldown"). Group
related changes into a single commit where reasonable.

## Reporting bugs / requesting features

Open an issue using the provided templates. For security-sensitive reports, see
[SECURITY.md](SECURITY.md) instead of filing a public issue.
