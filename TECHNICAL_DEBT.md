# Technical Debt

An honest inventory of known debt and improvement opportunities. None of these
block the app from working; they are what a reviewer would (rightly) flag, and
what should be paid down before this is treated as more than a single-user
project. Roughly ordered by impact.

## 1. Test coverage is a starter suite, not comprehensive (high priority)

A starter suite now exists in `backend/tests/` (57 tests) covering the
deterministic core — alert parsing, JD link rewriting + bot-wall/expiry
detection + HTML→Markdown nested lists, canonical-id dedup, preference matching,
and the agent tool-surface contract. What's still missing:

- **Route tests.** No FastAPI `TestClient` coverage of the HTTP layer
  (`routers/jobs.py` especially).
- **DB-backed integration tests.** Dedup/watermark are unit-tested as pure
  functions, but `run_ingest` end-to-end (against a temp DB + a faked Gmail
  client) is not.
- **Provider-adapter contract tests.** `agent/providers.py` adapters aren't
  exercised against a recorded/mocked stream for each provider.
- **Frontend tests.** None (no Vitest/RTL).

**Plan:** add a temp-DB fixture and route tests, mock the Gmail/LLM clients for
an ingestion integration test, record one stream per provider for adapter
contract tests, and introduce Vitest for the frontend. Wire all of it into CI
(see #2).

## 2. CI gate exists but is not yet comprehensive

`.github/workflows/ci.yml` now runs on every PR and on pushes to main
(GitHub-hosted): backend `pytest` and frontend `tsc -b && vite build`. Remaining
gaps:

- **No lint / type-check / static analysis** in CI — no `ruff`, `mypy`, or
  `eslint` step yet (see #3).
- **Deploy isn't gated on CI.** `deploy.yml` (self-hosted) runs independently on
  push to main, so a red CI run doesn't block the NAS deploy. **Plan:** gate the
  deploy on the CI workflow succeeding (e.g. `workflow_run` or a required check).

## 3. No linter / formatter / type-checker configured

No `ruff`/`black`/`mypy` config for Python and no `eslint`/`prettier` config for
the frontend are committed. The code is clean and consistent today, but nothing
enforces it. **Plan:** add `ruff` + `mypy` (with `pyproject.toml`) and ESLint +
Prettier, plus a `pre-commit` config.

## 4. Loose dependency pinning

`backend/requirements.txt` uses `>=` constraints with no lock file, so builds
aren't reproducible — a transitive update could change behavior between two NAS
deploys of the same commit. The frontend is fine (`package-lock.json` is
committed). **Plan:** pin via `pip-tools`/`uv` and commit a lock file.

## 5. `routers/jobs.py` is doing too much (429 lines)

The architectural rule is "routers thin, logic in services," and most routers
honor it — but `jobs.py` has grown to ~429 lines and mixes querying, filtering,
sorting, and mutation handling inline. **Plan:** extract a `services/jobs.py`
(or split query vs. mutation services) so the router is wiring again.

## 6. `App.tsx` holds all UI state (391 lines)

The SPA deliberately has no router; view switching, multi-select, and mutation
wiring all live in `App.tsx`. It's readable now but is the component most likely
to become a maintenance bottleneck. **Plan:** extract view containers and a
small amount of state into hooks/context as features grow; consider a router if
deep-linking is ever needed.

## 7. In-process scheduler couples ingestion to the web process

APScheduler runs inside the FastAPI process. It's the right call for a single
NAS (no extra worker), but it means a long ingest shares the web process, and
horizontal scaling isn't possible. The concurrency lock mitigates double-runs.
**Plan (only if scaling):** move ingestion to a separate worker/queue.

## 8. Single-user assumptions are baked in

There is no authentication or multi-tenancy — security comes entirely from the
network boundary (Tailscale + outbound-only). That is appropriate for the stated
scope, but it is a hard ceiling. **Plan (only if going multi-user):** add
authn/authz and per-user data scoping; the configurable DB URL already allows
Postgres.

## 9. In-memory state that doesn't survive a restart

The ingest `status` dict and the per-host bot-wall cooldown are module-level
in-memory state. Fine for a long-lived single process; lost on restart and not
shared across processes. **Plan:** persist cooldowns to the `meta` table if
restarts during ingest become common.

## 10. Observability is minimal

There's request-logging middleware and per-turn token traces, but no metrics,
tracing, or error aggregation. **Plan:** structured logs to a sink + basic
counters (ingest success/fail, fetch challenge rate, LLM spend) if this runs
unattended for long.

## 11. Scraping fragility (inherent, not fixable, but worth naming)

JD fetching depends on third-party HTML structure and anti-bot behavior that
changes without notice. The deterministic-first + cooldown design contains the
blast radius, but breakage is a *when*, not an *if*. Tests (#1) around the
parsers make regressions visible faster.

---

See [ROADMAP.md](ROADMAP.md) for feature direction and
[PORTFOLIO_REVIEW.md](PORTFOLIO_REVIEW.md) for the broader self-assessment.
