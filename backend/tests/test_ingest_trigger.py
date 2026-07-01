"""The /api/ingest/run trigger must flip status.running True *before* returning,
so the UI's first status poll doesn't see a stale running:false (BackgroundTasks
execute after the response).
"""
from fastapi import BackgroundTasks

from app.routers.ingest import trigger_ingest
from app.services.ingest import status


def test_trigger_marks_running_synchronously():
    status["running"] = False
    try:
        # The background task is registered on `bt` but not executed here, so
        # run_ingest never actually calls Gmail — we only check the sync flag.
        res = trigger_ingest(BackgroundTasks(), since_epoch=None, fetch_all=False)
        assert res == {"started": True}
        assert status["running"] is True
        assert status.get("phase") == "starting"
    finally:
        status["running"] = False


def test_trigger_reports_already_running():
    status["running"] = True
    try:
        res = trigger_ingest(BackgroundTasks(), since_epoch=None, fetch_all=False)
        assert res["started"] is False
        assert "already running" in res["detail"].lower()
    finally:
        status["running"] = False
