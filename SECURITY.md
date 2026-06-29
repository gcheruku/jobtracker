# Security Policy

## Reporting a vulnerability

If you discover a security issue, please **do not open a public issue**. Email
the maintainer at **gcheruku@gmail.com** with details and steps to reproduce.
You can expect an acknowledgement within a few days.

## Threat model & design posture

JobTrack is a single-user, self-hosted application. Its security posture is built
around keeping the attack surface small:

- **Outbound-only.** The NAS exposes no inbound ports. Deploys, LLM calls, JD
  fetches, and Gmail reads are all outbound. Remote access is via **Tailscale**
  (WireGuard mesh VPN), so the app is never on the public internet.
- **Same-origin API + locked CORS.** The SPA calls `/api` through the nginx
  proxy (same-origin). CORS defaults to localhost dev origins (not `*`), so a
  malicious page in the user's browser cannot read the API or issue preflighted
  writes to a VPN-reachable instance. Override with `JOBTRACKER_CORS_ORIGINS`.
- **Read-only AI tools.** The agent's tools cannot mutate the pipeline, and the
  tool-use loop is capped at 8 steps. See [docs/AI-Agent.md](docs/AI-Agent.md).
- **Least-privilege Gmail scope.** Ingestion uses `gmail.readonly` only.

## Secrets & personal data

Nothing personal is committed. The following are **gitignored** and must stay
local (or in the NAS `/data` volume):

- `.env` (LLM/Gmail config and keys)
- `jobs.db` and any `jobs.db.backup-*`
- `backend/secrets/credentials.json`, `backend/secrets/token.json`
- `Resume.docx` (and any `*.docx`)

Only `*.example.json` templates and `.env.example` files are committed. If you
fork this repo for real use, keep it **private** — the deploy runner mounts
`docker.sock`, which is root-equivalent on the host.

## Supported versions

This is an actively developed personal project; only the latest `main` is
supported.
