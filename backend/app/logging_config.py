"""Console logging setup for the API.

Gives readable, timestamped logs on stdout for app events and every HTTP request.
Verbosity is controlled by the JOBTRACKER_LOG_LEVEL env var (default INFO).
"""
from __future__ import annotations

import logging
import os

LOG_LEVEL = os.environ.get("JOBTRACKER_LOG_LEVEL", "INFO").upper()

# Shared application logger used across modules.
logger = logging.getLogger("jobtrack")


def setup_logging() -> None:
    level = getattr(logging, LOG_LEVEL, logging.INFO)

    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
            datefmt="%H:%M:%S",
        )
    )

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    logger.setLevel(level)
    # Let uvicorn's access/error logs flow through the same handler/format.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        lg = logging.getLogger(name)
        lg.handlers.clear()
        lg.propagate = True
