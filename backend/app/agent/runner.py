"""Entry point for the career assistant: pick the provider, then run its loop.

The provider (anthropic | gemini | openai) is chosen in Settings, falling back
to the AGENT_PROVIDER default. The provider-specific tool-use loops live in
`providers`; this module only resolves the selection.
"""
from __future__ import annotations

from typing import Iterator

from sqlmodel import Session

from ..config import AGENT_PROVIDER
from ..database import engine
from ..services.preferences import load_settings
from . import providers


def selected_provider() -> str:
    """The provider chosen in Settings, or the configured default."""
    try:
        with Session(engine) as session:
            pref = (load_settings(session).agent_provider or "").strip().lower()
    except Exception:
        pref = ""
    provider = pref or (AGENT_PROVIDER or "anthropic").lower()
    return provider if provider in providers.PROVIDERS else "anthropic"


def run_agent(history: list[dict], user_message: str) -> Iterator[dict]:
    yield from providers.run(selected_provider(), history, user_message)
