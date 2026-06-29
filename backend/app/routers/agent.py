"""Agent chat endpoint — streams the assistant's turn over SSE."""
from __future__ import annotations

import json
from typing import Iterator, Literal, Optional

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..agent import providers
from ..agent.runner import run_agent, selected_provider

router = APIRouter(prefix="/api/agent", tags=["agent"])


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    message: str
    history: Optional[list[ChatTurn]] = None


@router.get("/status")
def agent_status() -> dict:
    """Selected provider, which providers have a key, and whether the selected
    one is usable. Drives the Settings dropdown and the chat 'missing key' warning."""
    provider = selected_provider()
    keys = {p: bool(providers.provider_key(p)) for p in providers.PROVIDERS}
    return {
        "provider": provider,
        "providers": keys,
        "labels": providers.PROVIDER_LABELS,
        "enabled": keys.get(provider, False),
    }


def _sse(events: Iterator[dict]) -> Iterator[str]:
    for event in events:
        yield f"data: {json.dumps(event)}\n\n"


@router.post("/chat")
def chat(req: ChatRequest) -> StreamingResponse:
    history = [{"role": t.role, "content": t.content} for t in (req.history or [])]
    stream = _sse(run_agent(history, req.message))
    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
