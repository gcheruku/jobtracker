# Pre-Public Audit

Audit performed before preparing this repository for public release. **Result:
clean** — no secrets, credentials, or personal data are tracked or present in git
history.

## Method

- Listed all tracked files (`git ls-files`) and cross-checked sensitive patterns.
- Searched full git history for committed secrets / data files
  (`git log --all` over `*.env`, `*.db`, `*token*`, `*credential*`, `*.docx`).
- Grepped historical blobs for key-shaped strings (`AIza…`, `sk-…`,
  `-----BEGIN …`).

## Findings

### Tracked files — all clean

The repository tracks only source, configuration templates, and documentation.
No real secrets or personal data are committed. Verified that the following are
**present locally but correctly gitignored and untracked**:

| Item | Status |
|---|---|
| `jobs.db`, `jobs.db.backup-*` | Untracked (gitignored) — real personal job data |
| `Resume.docx` | Untracked (gitignored via `*.docx`) |
| `backend/secrets/credentials.json`, `token.json` | Untracked (gitignored); only `*.example.json` committed |
| `.env` (any) | Untracked (gitignored) |
| `.DS_Store`, `__pycache__/`, `backend/.venv/`, `frontend/node_modules/` | Untracked (gitignored) |
| `.claude/` | Untracked (gitignored) |

### Git history — clean

No `.env`, database, OAuth token, credential, or `.docx` file has ever been
committed. No key-shaped strings were found in historical blobs. The one history
hit for secrets-adjacent paths (`c44f37b`) touched only `*.example.json`
templates and setup docs.

### Committed artifacts reviewed and kept (intentional)

- `backend/secrets/*.example.json`, `*.env.example` — templates, no real values.
- `prompts/*.md` — the build prompts, kept for provenance.

## Actions taken during prep

- Added `go_public.md` (the repo-prep prompt) to `.gitignore` — local working
  note, not part of the public project.
- Removed `prompts/figma_design.png` and `prompts/reference_email_parsers.py`
  from the repo (kept local only).
- Moved the personal/local `ARCHITECTURE.md` into a polished, public
  [`docs/Architecture.md`](Architecture.md) and removed the local-only copy and
  its `.gitignore` exclusion.
- Consolidated deployment docs into [`docs/Deployment.md`](Deployment.md);
  `deploy/README.md` is now a short pointer.

## Recommendation

The repository is safe to publish. Note that anyone *self-hosting* a fork should
keep it **private**, because the deploy runner mounts `docker.sock`
(root-equivalent on the host) — see [SECURITY.md](../SECURITY.md).
