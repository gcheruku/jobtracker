# Deploying JobTrack to Synology (private, via a self-hosted runner)

The NAS only makes **outbound** calls to GitHub — no port-forwarding, nothing
inbound. A self-hosted runner container picks up the workflow, builds the images
on the NAS, and runs them with `docker compose`.

## What gets deployed
- `frontend` (nginx) on `http://<NAS-IP>:8080` — serves the UI and proxies `/api`.
- `backend` (uvicorn) — internal only; reachable via the frontend proxy.
- A NAS folder `DATA_DIR` mounted at `/data` holds everything personal:
  `jobs.db`, `secrets/`, `Resume.docx`, `.env`, `hf-cache/`, `uploads/`.

---

## Step 1 — Create the data folder on the NAS (one time)

SSH into the NAS (Control Panel → Terminal & SNMP → enable SSH), then:

```bash
sudo mkdir -p /volume1/docker/jobtracker/data/secrets
cd /volume1/docker/jobtracker/data

# Bring over your personal files (e.g. via File Station or scp):
#   jobs.db                      -> ./jobs.db          (optional; created fresh if absent)
#   backend/secrets/credentials.json, token.json -> ./secrets/
#   Resume.docx                  -> ./Resume.docx

# App secrets (NOT in git):
cat > .env <<'EOF'
GOOGLE_API_KEY=your-gemini-key
# GEMINI_MODEL=gemini-2.5-flash
# GMAIL_LABEL=Job alerts
# INGEST_INTERVAL_HOURS=4
EOF
```

> The backend reads `/data/.env` automatically. If you have no `jobs.db`, the app
> creates an empty one on first start.

## Step 2 — Register a self-hosted runner (one time)

Authenticate the runner with a **Personal Access Token via `ACCESS_TOKEN`**, not
a one-time registration token. The image re-registers on every container start,
and a registration token expires in ~1 hour — so a `RUNNER_TOKEN` sends the
container into a register-fail → exit → restart loop once it lapses. With
`ACCESS_TOKEN` the entrypoint mints a fresh registration token from the GitHub
API on each boot, so restarts always work.

1. Create a **classic PAT** with the **`repo`** scope: GitHub → **Settings →
   Developer settings → Personal access tokens → Tokens (classic)**. A finite
   expiry (e.g. 1 year) is fine — when it expires the runner loops again, so
   rotate the PAT and rebuild. Keep the token out of git.
2. In **Container Manager → Registry**, download `myoung34/github-runner:latest`.
3. **Container Manager → Container → Create** from that image with:
   - **Volume:** map `/var/run/docker.sock` → `/var/run/docker.sock` (lets the
     runner build/run containers on the NAS).
   - **Environment:**
     - `REPO_URL=https://github.com/<you>/jobtracker`
     - `ACCESS_TOKEN=<your classic PAT, `repo` scope>`
     - `RUNNER_NAME=synology`
     - `LABELS=self-hosted`
     - `RUNNER_SCOPE=repo`
   - Enable auto-restart.

   (CLI equivalent over SSH:)
   ```bash
   docker run -d --restart unless-stopped --name gh-runner \
     -v /var/run/docker.sock:/var/run/docker.sock \
     -e REPO_URL=https://github.com/<you>/jobtracker \
     -e ACCESS_TOKEN=<your-PAT> \
     -e RUNNER_NAME=synology -e LABELS=self-hosted -e RUNNER_SCOPE=repo \
     myoung34/github-runner:latest
   ```
   The runner should appear **Idle** under Settings → Actions → Runners.

4. (If your data path isn't the default) set repo **Variables** `DATA_DIR` and
   `WEB_PORT` under Settings → Secrets and variables → Actions → Variables.

## Step 3 — Deploy

Push to `main` (or run the **Deploy to Synology** workflow manually via
Actions → Run workflow). The runner builds the images on the NAS and starts the
stack.

By default this builds the **slim backend** (no PyTorch) — fast to build and runs
in well under 1 GB RAM, ideal for a 2 GB DS220+. The Gemini "Compare with Resume"
feature works in slim mode; only the *offline* semantic resume↔JD matching is
omitted. To enable it on a higher-RAM host, set a repo **Variable**
`WITH_SEMANTIC=true` (Settings → Secrets and variables → Actions → Variables) and
re-deploy.

## Step 4 — Use it

Open `http://<NAS-IP>:8080`. Click **Fetch alerts** to ingest (needs the Gmail
files in `secrets/`); the resume comes from `/data/Resume.docx`.

---

## Notes
- **Security:** mounting `docker.sock` gives the runner root-equivalent access to
  the NAS — fine for a private repo you control. Keep the repo private.
- **Resources:** the default slim backend has no Torch and is small. Only the
  `WITH_SEMANTIC=true` build is large (Torch + `hf-cache`) and wants ~2 GB free
  RAM; don't enable it on a 2 GB DS220+.
- **Backend `/docs`:** to reach the API docs directly, add `ports: ["8000:8000"]`
  to the backend service (otherwise it's internal-only).
- **Rollback:** images are tagged `:latest`; to roll back, deploy an earlier
  commit (Actions → re-run, or `git revert`). Your data in `DATA_DIR` is never
  touched by deploys.
- **Logs:** `docker logs jobtracker-backend` / `jobtracker-frontend` over SSH, or
  in Container Manager.
