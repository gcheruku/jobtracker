"""The agent loop: plan → call tools → observe → repeat, streamed to the UI.

A hand-written loop (not the SDK tool-runner) so we can stream text token-by-
token, emit tool-activity events for the UI, trace token usage, and cap the
number of steps. Read-only tools mean no approval gate is needed yet.
"""
from __future__ import annotations

import json
from typing import Iterator

from ..config import ANTHROPIC_API_KEY, ANTHROPIC_MODEL
from ..logging_config import logger
from .tools import EXECUTORS, TOOLS

# Cap the agent loop so a misbehaving plan can't spin forever / burn tokens.
_MAX_STEPS = 8
_MAX_TOKENS = 8192

_SYSTEM = (
    "You are JobTrack's career assistant, embedded in the user's personal job-"
    "search tracker. You help them reason about the jobs in their pipeline and "
    "their resume.\n\n"
    "You have tools to search their pipeline, read a job's details/description, "
    "get pipeline stats, and compare a job against their resume. Prefer calling a "
    "tool over guessing — always ground answers in their actual data, and cite "
    "the company/role you're referring to. When you list jobs, keep it tight and "
    "scannable. If a tool returns an error, explain it plainly and suggest a next "
    "step. Be concise and practical; you're a working tool, not a chatbot."
)


def _client():
    import anthropic

    return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def _run_tool(name: str, tool_input: dict) -> tuple[str, bool]:
    """Execute one tool call; return (json_result, is_error)."""
    fn = EXECUTORS.get(name)
    if fn is None:
        return json.dumps({"error": f"Unknown tool {name!r}"}), True
    try:
        result = fn(tool_input or {})
        return json.dumps(result, default=str), bool(result.get("error"))
    except Exception as exc:  # never let a tool crash the loop
        logger.exception("Agent tool %s failed", name)
        return json.dumps({"error": str(exc)}), True


def run_agent(history: list[dict], user_message: str) -> Iterator[dict]:
    """Drive the agent and yield UI events:

      {"type": "text", "text": ...}            streamed assistant text
      {"type": "tool_use", "name", "input"}    a tool the agent decided to call
      {"type": "tool_result", "name", "is_error"}  that tool's outcome
      {"type": "usage", "input_tokens", "output_tokens"}  per-turn token trace
      {"type": "done"} | {"type": "error", "message": ...}
    """
    if not ANTHROPIC_API_KEY:
        yield {"type": "error", "message": "The assistant isn't configured (no ANTHROPIC_API_KEY)."}
        return

    client = _client()
    # The conversation: prior turns + this user message. The API is stateless,
    # so we resend the full transcript each step.
    messages: list[dict] = [*history, {"role": "user", "content": user_message}]

    try:
        for _step in range(_MAX_STEPS):
            with client.messages.stream(
                model=ANTHROPIC_MODEL,
                max_tokens=_MAX_TOKENS,
                system=_SYSTEM,
                tools=TOOLS,
                thinking={"type": "adaptive"},
                messages=messages,
            ) as stream:
                for text in stream.text_stream:
                    yield {"type": "text", "text": text}
                final = stream.get_final_message()

            if final.usage:
                yield {
                    "type": "usage",
                    "input_tokens": final.usage.input_tokens,
                    "output_tokens": final.usage.output_tokens,
                }

            if final.stop_reason != "tool_use":
                yield {"type": "done"}
                return

            # Execute every tool the model requested, then feed results back.
            messages.append({"role": "assistant", "content": final.content})
            tool_results = []
            for block in final.content:
                if block.type != "tool_use":
                    continue
                yield {"type": "tool_use", "name": block.name, "input": block.input}
                result_json, is_error = _run_tool(block.name, block.input)
                yield {"type": "tool_result", "name": block.name, "is_error": is_error}
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result_json,
                    "is_error": is_error,
                })
            messages.append({"role": "user", "content": tool_results})

        yield {"type": "text", "text": "\n\n_(Reached the step limit — ask me to continue.)_"}
        yield {"type": "done"}
    except Exception as exc:
        logger.exception("Agent run failed")
        yield {"type": "error", "message": str(exc)}
