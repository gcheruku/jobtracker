"""Shared test setup.

Point the database at a throwaway temp file *before* any `app.*` module is
imported, so importing modules that construct the SQLModel engine (e.g.
`app.services.preferences`, `app.agent.tools`) can never touch the real
`jobs.db`. The unit tests here exercise pure functions and don't query the DB;
this is purely a safety net against import-time side effects.
"""
from __future__ import annotations

import os
import tempfile

_tmp_db = os.path.join(tempfile.gettempdir(), "jobtracker_test.db")
# Start each test session from a clean DB so the schema always matches the
# current models (create_all never ALTERs an existing table, so a stale file
# would be missing newly-added columns).
if os.path.exists(_tmp_db):
    os.remove(_tmp_db)
os.environ.setdefault("JOBTRACKER_DATABASE_URL", f"sqlite:///{_tmp_db}")
# Keep tests hermetic: no real keys, deterministic provider default.
os.environ.setdefault("ANTHROPIC_API_KEY", "")
os.environ.setdefault("GOOGLE_API_KEY", "")
os.environ.setdefault("OPENAI_API_KEY", "")
