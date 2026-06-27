// Streaming client for the Claude agent chat endpoint (Server-Sent Events over
// a POST). The browser EventSource API is GET-only, so we read the response
// body stream manually and parse `data:` frames.

const BASE = import.meta.env.VITE_API_BASE ?? "";

export type AgentEvent =
  | { type: "text"; text: string }
  | { type: "tool_use"; name: string; input: unknown }
  | { type: "tool_result"; name: string; is_error: boolean }
  | { type: "usage"; input_tokens: number; output_tokens: number }
  | { type: "done" }
  | { type: "error"; message: string };

export type AgentTurn = { role: "user" | "assistant"; content: string };

export async function agentEnabled(): Promise<boolean> {
  try {
    const r = await fetch(`${BASE}/api/agent/status`);
    return r.ok && (await r.json()).enabled === true;
  } catch {
    return false;
  }
}

export async function streamAgentChat(
  body: { message: string; history: AgentTurn[] },
  onEvent: (e: AgentEvent) => void,
  signal?: AbortSignal
): Promise<void> {
  const res = await fetch(`${BASE}/api/agent/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok || !res.body) {
    throw new Error(`${res.status} ${await res.text().catch(() => "")}`);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    // SSE frames are separated by a blank line.
    const frames = buf.split("\n\n");
    buf = frames.pop() ?? "";
    for (const frame of frames) {
      const line = frame.split("\n").find((l) => l.startsWith("data:"));
      if (!line) continue;
      const json = line.slice(5).trim();
      if (!json) continue;
      try {
        onEvent(JSON.parse(json) as AgentEvent);
      } catch {
        /* ignore malformed frame */
      }
    }
  }
}
