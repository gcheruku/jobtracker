# deploy/

Docker Compose stack and the self-hosted GitHub Actions runner config for the
Synology NAS deployment.

| File | Purpose |
|---|---|
| `docker-compose.yml` | `frontend` (nginx) + `backend` (uvicorn) services |
| `.env.example` | Template for `deploy/.env` (`DATA_DIR`, `WEB_PORT`, `WITH_SEMANTIC`) |
| `gh-runner.example.yml` | Self-hosted runner config (`ACCESS_TOKEN` / PAT) |

**Full deployment guide — NAS setup, runner registration, CI/CD pipeline, and
operations — lives in [`../docs/Deployment.md`](../docs/Deployment.md).**
