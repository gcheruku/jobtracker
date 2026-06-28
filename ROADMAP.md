# Roadmap

Directional, not a commitment. Items reflect where the architecture is designed
to grow.

## Near term

- **Agent write tools behind an approval inbox.** Promote `set_status`, `skip`,
  and `add_note` tools, gated by a human-in-the-loop approval queue so no action
  is taken without confirmation. (Read-only is intentional in v1.)
- **Automated tests.** Unit tests for the parsers (`alert_parsers.py`), JD link
  rewriting (`jd_fetch.py`), dedup/watermark logic, and preference matching;
  contract tests for each agent provider adapter against the neutral event
  stream.
- **Eval harness.** Turn the user's accept/skip history into labels and grade the
  triage/scoring with an LLM-as-judge (precision/recall).

## Medium term

- **Autonomous daily agent.** A scheduled run: ingest → triage → research top
  matches → produce a daily briefing of proposed actions for review.
- **Multi-agent orchestration.** Specialized extractor / scorer / researcher /
  writer agents coordinated by the runner.
- **Pluggable persistence.** Formalize the Postgres path (the DB URL already
  supports it) for multi-device use.

## Longer term / exploratory

- **More sources.** Additional job boards and ATS integrations behind the same
  deterministic-first ingestion contract.
- **Retrieval upgrades.** A vector store for résumé/JD chunks to sharpen semantic
  matching and ground the assistant's answers.
- **Cost dashboards.** Aggregate the per-turn token traces into spend reporting.

See also [TECHNICAL_DEBT.md](TECHNICAL_DEBT.md) for the cleanup that should land
alongside these.
