# Portfolio Review

A candid, deliberately critical self-review of this repository as it would be
read by senior engineers and engineering leaders (the kind who interview at
Microsoft, Google, Amazon, OpenAI, Anthropic, Stripe, Nvidia, Databricks, and
major financial institutions). The goal is to be useful, not flattering.

---

## Strengths

1. **Real, end-to-end system — not a tutorial clone.** Email ingestion → parsing
   → anti-bot JD fetch → multi-signal scoring → pipeline UI → agentic chat, all
   running in production on real hardware with push-to-deploy. The breadth is
   credible.
2. **The multi-LLM agent is a genuine differentiator.** A hand-written tool-use
   loop with a *neutral event contract* and three provider adapters
   (Anthropic/Gemini/OpenAI), selectable at runtime, with read-only guardrails
   and token tracing. This is the part most worth interviewing on, and it's
   designed, not bolted on. See [docs/AI-Agent.md](docs/AI-Agent.md).
3. **Hard sub-problem solved well.** The per-host anti-bot strategy (diagnosing
   that the *TLS fingerprint*, not headers, was the gate, and that Glassdoor
   wants the opposite client from Indeed) plus a host-scoped cooldown is a strong,
   specific story.
4. **Sound architecture discipline.** Thin routers / fat services, centralized
   config, idempotent incremental ingestion (watermark + canonical-id dedup),
   and graceful degradation as a contract (the app works with zero keys).
5. **Pragmatic, defensible infra choices.** Outbound-only, self-hosted runner +
   Tailscale = push-to-deploy with no public surface and no cloud bill. Bundle
   perf work (~50% JS reduction) is *measured*, with SSR explicitly considered
   and rejected for good reasons.
6. **Documentation is above average for a personal project.** Architecture,
   AI-Agent, Deployment, and Development docs with rendering Mermaid diagrams.

## Weaknesses

1. **Thin test coverage.** A starter suite now covers the deterministic core
   (parsers, dedup, link rewriting, preference matching, tool-surface contract —
   57 tests), but there are still no route tests, no DB-backed ingestion
   integration test, no provider-adapter contract tests, and no frontend tests.
   See [TECHNICAL_DEBT.md](TECHNICAL_DEBT.md#1-test-coverage-is-a-starter-suite-not-comprehensive-high-priority).
2. **CI gate is new and partial.** A `ci.yml` now runs backend tests + the
   frontend build on PRs/main, but there's no lint/type-check step yet, and the
   self-hosted deploy isn't gated on CI passing.
3. **No enforced code quality tooling.** No ruff/mypy/eslint/prettier/pre-commit
   committed. The code is clean *today*, but nothing keeps it that way.
4. **Reproducibility gap.** `requirements.txt` uses `>=` with no lock file.
5. **A couple of files are outgrowing their role** — `routers/jobs.py` (~429
   lines) violates the project's own "thin router" rule, and `App.tsx` (~391
   lines) concentrates all UI state.
6. **Security rests entirely on the network boundary.** No authn/authz; the
   `docker.sock` mount is root-equivalent on the host. Correct for the single-user
   scope and clearly documented, but a hard ceiling and worth stating up front.

## Suggestions (in priority order)

1. Done: a starter test suite + a `ci.yml` that runs tests and the frontend build
   on PRs. Next: add lint + type-check (ruff/mypy/eslint) to CI, extend tests
   (route + integration + provider adapters), and gate the deploy on CI.
2. Add ruff + mypy + ESLint + Prettier + pre-commit; pin Python deps with a lock
   file.
3. Refactor `routers/jobs.py` into a `services/jobs.py`; decompose `App.tsx`.
4. Add real screenshots (placeholders are in `docs/screenshots/`).
5. Add a tiny eval harness for the scoring/triage (LLM-as-judge over accept/skip
   history) — it would showcase AI-systems maturity strongly.

## Missing documentation

- An API reference beyond the auto-generated `/docs` (a short endpoint table).
- A short "design decisions / trade-offs" ADR log (some of this lives in the
  architecture doc but isn't captured as decisions).
- Test strategy doc (once tests exist).

## Security concerns

- No application-layer auth (mitigated by Tailscale + outbound-only; documented).
- `docker.sock` mount is root-equivalent (documented; keep forks private).
- LLM keys and the Gmail token live in `/data/.env` (gitignored; acceptable for
  self-hosting, not a managed secret store).
- **No secrets are committed and none appear in git history** (verified). The
  `.gitignore` correctly excludes `.env`, `jobs.db`, OAuth files, and `*.docx`.

## Interview talking points

- **Provider-agnostic agent core, provider-specific edges** — one neutral event
  contract, three thin adapters; adding a provider is one function.
- **Why an agent vs. a single prompt** — open-ended questions over live per-user
  data require the model to *decide* what to read and compare (tool use + loop).
- **Diagnosing the anti-bot gate as a TLS-fingerprint problem**, and why Glassdoor
  needed the opposite client from Indeed; the cooldown that keeps the home IP
  from being re-flagged.
- **Deterministic-first ingestion** — parse Indeed/Glassdoor with regex/BS4 before
  paying for an LLM; it's cheaper, more reliable, and captures salary.
- **Idempotent incremental ingestion** — watermark + canonical-id dedup makes
  resent alerts safe.
- **Bundle perf without SSR** — measured ~50% JS cut; SSR considered and rejected
  with a reason.
- **Graceful degradation as a contract** — the whole app runs with zero keys.

## Estimated quality score

**7 / 10** as a portfolio piece for senior/staff and AI-leadership roles.

- The architecture, the multi-LLM agent, and the infra story are genuinely strong
  (8–9 territory on design and breadth).
- The absence of tests and CI quality gates is what holds the score down; for the
  bar at the named companies, untested code is the most common single reason a
  strong project reads as "impressive prototype" rather than "production
  engineer." Closing #1–#3 in [TECHNICAL_DEBT.md](TECHNICAL_DEBT.md) would move
  this to a solid 8.5–9.

## Recommendations before making the repository public

- [x] Verify no secrets are committed or in git history (done — clean).
- [x] Confirm `.env`, `jobs.db`/backups, OAuth tokens, and the resume are
      gitignored (done).
- [x] Professional README, docs set, diagrams, and GitHub project files (done).
- [x] Add a starter test suite (done — `backend/tests/`, 57 pytest tests over the
      deterministic core). Still recommended: route/integration tests + a CI
      quality gate (see [TECHNICAL_DEBT.md](TECHNICAL_DEBT.md#1-test-coverage-is-a-starter-suite-not-comprehensive-high-priority)).
- [ ] Add real screenshots.
- [ ] Decide whether to keep the published copy public given it deploys via a
      `docker.sock`-mounted runner; the **code** is safe to publish, but anyone
      self-hosting should keep their fork private.
