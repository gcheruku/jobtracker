"""Provider backends for the career assistant.

The same shared tool surface (`tools.TOOLS` / `tools.EXECUTORS`) is driven by one
of three LLM providers — Anthropic, Gemini, or OpenAI — selectable in Settings.
Each `_run_*` function runs that provider's native tool-use loop and yields the
same neutral UI events, so the runner/router/frontend stay provider-agnostic:

    {"type": "text", "text"}                 streamed assistant text
    {"type": "tool_use", "name", "input"}    a tool the model decided to call
    {"type": "tool_result", "name", "is_error"}
    {"type": "usage", "input_tokens", "output_tokens"}
    {"type": "done"} | {"type": "error", "message"}
"""
from __future__ import annotations

import json
from typing import Iterator

from ..config import (
    ANTHROPIC_API_KEY,
    ANTHROPIC_MODEL,
    GEMINI_MODEL,
    GOOGLE_API_KEY,
    OPENAI_API_KEY,
    OPENAI_MODEL,
)
from ..logging_config import logger
from .tools import EXECUTORS, TOOLS

PROVIDERS = ("anthropic", "gemini", "openai")
PROVIDER_LABELS = {"anthropic": "Anthropic (Claude)", "gemini": "Google Gemini", "openai": "OpenAI"}

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


def provider_key(provider: str) -> str:
    return {
        "anthropic": ANTHROPIC_API_KEY,
        "gemini": GOOGLE_API_KEY,
        "openai": OPENAI_API_KEY,
    }.get(provider, "")


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


def run(provider: str, history: list[dict], user_message: str) -> Iterator[dict]:
    """Dispatch to the selected provider, after checking its key is configured."""
    if provider not in PROVIDERS:
        provider = "anthropic"
    if not provider_key(provider):
        label = PROVIDER_LABELS.get(provider, provider)
        yield {"type": "error", "message": f"{label} has no API key configured. Add one or pick another provider in Settings."}
        return
    try:
        if provider == "anthropic":
            yield from _run_anthropic(history, user_message)
        elif provider == "gemini":
            yield from _run_gemini(history, user_message)
        else:
            yield from _run_openai(history, user_message)
    except Exception as exc:
        logger.exception("Agent run failed (%s)", provider)
        yield {"type": "error", "message": str(exc)}


# --- Anthropic ----------------------------------------------------------------

def _run_anthropic(history: list[dict], user_message: str) -> Iterator[dict]:
    import anthropic

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    messages: list[dict] = [*history, {"role": "user", "content": user_message}]

    for _ in range(_MAX_STEPS):
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
            yield {"type": "usage", "input_tokens": final.usage.input_tokens, "output_tokens": final.usage.output_tokens}

        if final.stop_reason != "tool_use":
            yield {"type": "done"}
            return

        messages.append({"role": "assistant", "content": final.content})
        results = []
        for block in final.content:
            if block.type != "tool_use":
                continue
            yield {"type": "tool_use", "name": block.name, "input": block.input}
            result_json, is_error = _run_tool(block.name, block.input)
            yield {"type": "tool_result", "name": block.name, "is_error": is_error}
            results.append({"type": "tool_result", "tool_use_id": block.id, "content": result_json, "is_error": is_error})
        messages.append({"role": "user", "content": results})

    yield {"type": "text", "text": "\n\n_(Reached the step limit — ask me to continue.)_"}
    yield {"type": "done"}


# --- OpenAI -------------------------------------------------------------------

def _openai_tools() -> list[dict]:
    return [
        {"type": "function", "function": {"name": t["name"], "description": t["description"], "parameters": t["input_schema"]}}
        for t in TOOLS
    ]


def _run_openai(history: list[dict], user_message: str) -> Iterator[dict]:
    from openai import OpenAI

    client = OpenAI(api_key=OPENAI_API_KEY)
    messages: list[dict] = [
        {"role": "system", "content": _SYSTEM},
        *history,
        {"role": "user", "content": user_message},
    ]
    tools = _openai_tools()

    for _ in range(_MAX_STEPS):
        stream = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            tools=tools,
            max_tokens=_MAX_TOKENS,
            stream=True,
            stream_options={"include_usage": True},
        )
        content = ""
        calls: dict[int, dict] = {}  # index -> {id, name, args}
        usage = None
        for chunk in stream:
            usage = getattr(chunk, "usage", None) or usage
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta and delta.content:
                content += delta.content
                yield {"type": "text", "text": delta.content}
            for tc in (delta.tool_calls or []) if delta else []:
                slot = calls.setdefault(tc.index, {"id": "", "name": "", "args": ""})
                if tc.id:
                    slot["id"] = tc.id
                if tc.function and tc.function.name:
                    slot["name"] += tc.function.name
                if tc.function and tc.function.arguments:
                    slot["args"] += tc.function.arguments

        if usage:
            yield {"type": "usage", "input_tokens": getattr(usage, "prompt_tokens", 0), "output_tokens": getattr(usage, "completion_tokens", 0)}

        if not calls:
            yield {"type": "done"}
            return

        ordered = [calls[i] for i in sorted(calls)]
        messages.append({
            "role": "assistant",
            "content": content or None,
            "tool_calls": [
                {"id": c["id"], "type": "function", "function": {"name": c["name"], "arguments": c["args"] or "{}"}}
                for c in ordered
            ],
        })
        for c in ordered:
            try:
                args = json.loads(c["args"] or "{}")
            except Exception:
                args = {}
            yield {"type": "tool_use", "name": c["name"], "input": args}
            result_json, is_error = _run_tool(c["name"], args)
            yield {"type": "tool_result", "name": c["name"], "is_error": is_error}
            messages.append({"role": "tool", "tool_call_id": c["id"], "content": result_json})

    yield {"type": "text", "text": "\n\n_(Reached the step limit — ask me to continue.)_"}
    yield {"type": "done"}


# --- Gemini -------------------------------------------------------------------

def _run_gemini(history: list[dict], user_message: str) -> Iterator[dict]:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=GOOGLE_API_KEY)
    tools = [types.Tool(function_declarations=[
        {"name": t["name"], "description": t["description"], "parameters": t["input_schema"]}
        for t in TOOLS
    ])]
    config = types.GenerateContentConfig(system_instruction=_SYSTEM, tools=tools)

    contents: list = []
    for turn in history:
        role = "model" if turn["role"] == "assistant" else "user"
        contents.append(types.Content(role=role, parts=[types.Part(text=turn["content"])]))
    contents.append(types.Content(role="user", parts=[types.Part(text=user_message)]))

    for _ in range(_MAX_STEPS):
        fcalls = []
        model_parts = []
        for chunk in client.models.generate_content_stream(model=GEMINI_MODEL, contents=contents, config=config):
            for cand in (chunk.candidates or []):
                parts = getattr(getattr(cand, "content", None), "parts", None) or []
                for part in parts:
                    if getattr(part, "text", None):
                        yield {"type": "text", "text": part.text}
                        model_parts.append(types.Part(text=part.text))
                    fc = getattr(part, "function_call", None)
                    if fc:
                        fcalls.append(fc)
                        model_parts.append(types.Part(function_call=fc))

        if not fcalls:
            yield {"type": "done"}
            return

        contents.append(types.Content(role="model", parts=model_parts))
        response_parts = []
        for fc in fcalls:
            args = dict(fc.args or {})
            yield {"type": "tool_use", "name": fc.name, "input": args}
            result_json, is_error = _run_tool(fc.name, args)
            try:
                payload = json.loads(result_json)
            except Exception:
                payload = {"result": result_json}
            yield {"type": "tool_result", "name": fc.name, "is_error": is_error}
            response_parts.append(types.Part.from_function_response(name=fc.name, response=payload if isinstance(payload, dict) else {"result": payload}))
        contents.append(types.Content(role="user", parts=response_parts))

    yield {"type": "text", "text": "\n\n_(Reached the step limit — ask me to continue.)_"}
    yield {"type": "done"}
