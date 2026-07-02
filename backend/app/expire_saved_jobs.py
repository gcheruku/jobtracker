"""Sweep the Saved column and move expired postings to the Expired state.

Looks at every job that currently sits in the **Saved** column on the dashboard
— display status "Saved", not skipped, not preference-mismatched — and fetches
its posting page. Any that show an expiry banner ("no longer accepting
applications", "this job has expired", ...) OR whose page 404/410s are moved to
the "Expired" state (off the board, into the Inactive view). Starred (watchlist)
jobs are left untouched by design. A bot wall or fetch error never triggers a
move — the sweep only ever under-expires.

Run it as a module so it works both in local dev and inside the Docker image
(which contains the `app` package but not the backend/ project root):

    cd backend
    python -m app.expire_saved_jobs            # do the sweep
    python -m app.expire_saved_jobs --dry-run  # report only, no DB changes
    python -m app.expire_saved_jobs --limit 20 # first 20 (most recent) only

On the NAS (Docker), exec it in the running backend container:

    docker exec jobtracker-backend python -m app.expire_saved_jobs --dry-run

The actual logic lives in app.services.expiry.sweep_expired_saved, shared with
the in-process scheduler so a manual run and the scheduled run behave identically
(and can't run concurrently).
"""
from __future__ import annotations

import argparse
import sys

from sqlmodel import Session

from app.database import engine, init_db
from app.services.expiry import sweep_expired_saved

# How each per-job outcome renders on the console.
_LABELS = {
    "gone": "GONE (404)   ",
    "expired": "EXPIRED      ",
    "active": "active       ",
    "no_url": "SKIP (no URL)",
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument(
        "--dry-run", action="store_true",
        help="report which jobs would be expired without changing the database",
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="only check the first N Saved jobs (most recent first)",
    )
    parser.add_argument(
        "--delay", type=float, default=1.0,
        help="seconds to pause between fetches (default 1.0; keeps the IP off bot-walls)",
    )
    args = parser.parse_args(argv)

    # Idempotent, additive migration the app runs on startup — ensures newer
    # columns (watchlist, mismatched, ...) exist when the script runs standalone.
    init_db()

    def progress(i: int, total: int, outcome: str, label: str) -> None:
        print(f"[{i}/{total}] {_LABELS[outcome]}  {label}")

    with Session(engine) as session:
        mode = "DRY RUN — no changes will be saved" if args.dry_run else "moving expired jobs to Expired"
        print(f"Checking Saved (non-starred) jobs; {mode}.\n")
        s = sweep_expired_saved(
            session, dry_run=args.dry_run, limit=args.limit, delay=args.delay,
            progress=progress,
        )

    if s.get("skipped"):
        print("A sweep is already running; nothing to do.")
        return 0
    if s["total"] == 0:
        print("No Saved (non-starred) jobs to check.")
        return 0

    verb = "would be moved" if args.dry_run else "moved to Expired"
    print(
        f"\nDone. {s['moved']} {verb} "
        f"({s['expired']} expired banner, {s['gone']} gone/404), "
        f"{s['active']} still active, {s['no_url']} skipped (no URL)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
