"""Local convenience shim — the real CLI lives in app/expire_saved_jobs.py so it
also ships inside the Docker image.

    cd backend
    python expire_saved_jobs.py --dry-run          # local dev
    # in the container / on the NAS, run the module form:
    python -m app.expire_saved_jobs --dry-run
    docker exec jobtracker-backend python -m app.expire_saved_jobs --dry-run
"""
from __future__ import annotations

import sys

from app.expire_saved_jobs import main

if __name__ == "__main__":
    sys.exit(main())
