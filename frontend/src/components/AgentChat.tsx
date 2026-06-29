import { useEffect, useRef, useState } from "react";
import { Sparkles, X, Send, Loader2, Wrench, AlertCircle } from "lucide-react";
import { agentStatus, streamAgentChat, type AgentStatus, type AgentTurn } from "../lib/agent";
import { Markdown } from "./Markdown";

type ToolActivity = { name: string; error?: boolean; done?: boolean };

/**
 * Floating career-assistant: a Claude tool-using agent over the job pipeline.
 * Self-contained — manages its own open state and conversation, streams the
 * reply token-by-token, and surfaces which tools the agent calls.
 */
export function AgentChat() {
  const [open, setOpen] = useState(false);
  const [status, setStatus] = useState<AgentStatus | null>(null);
  const enabled = status ? status.enabled : null;
  const [messages, setMessages] = useState<AgentTurn[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [draft, setDraft] = useState(""); // assistant text as it streams
  const [tools, setTools] = useState<ToolActivity[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Re-check on every open so a provider switch in Settings is reflected.
  useEffect(() => {
    if (open) agentStatus().then(setStatus);
  }, [open]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages, draft, tools, open]);

  async function send() {
    const message = input.trim();
    if (!message || streaming) return;
    const history = messages;
    setMessages([...history, { role: "user", content: message }]);
    setInput("");
    setStreaming(true);
    setDraft("");
    setTools([]);

    let acc = "";
    try {
      await streamAgentChat({ message, history }, (e) => {
        if (e.type === "text") {
          acc += e.text;
          setDraft(acc);
        } else if (e.type === "tool_use") {
          setTools((t) => [...t, { name: e.name }]);
        } else if (e.type === "tool_result") {
          setTools((t) => {
            const next = [...t];
            for (let i = next.length - 1; i >= 0; i--) {
              if (next[i].name === e.name && !next[i].done) {
                next[i] = { ...next[i], done: true, error: e.is_error };
                break;
              }
            }
            return next;
          });
        } else if (e.type === "error") {
          acc += `${acc ? "\n\n" : ""}⚠️ ${e.message}`;
          setDraft(acc);
        }
      });
    } catch (err) {
      acc += `${acc ? "\n\n" : ""}⚠️ ${err instanceof Error ? err.message : "Request failed."}`;
    } finally {
      setMessages((m) => [...m, { role: "assistant", content: acc || "_(no response)_" }]);
      setDraft("");
      setTools([]);
      setStreaming(false);
    }
  }

  return (
    <>
      {/* Floating launcher */}
      {!open && (
        <button
          onClick={() => setOpen(true)}
          title="Career assistant"
          className="fixed bottom-5 right-5 z-40 flex h-12 w-12 items-center justify-center rounded-full bg-indigo-600 text-white shadow-xl transition hover:bg-indigo-700"
        >
          <Sparkles size={20} />
        </button>
      )}

      {open && (
        <div className="fixed inset-y-0 right-0 z-50 flex w-full flex-col border-l border-slate-200 bg-white shadow-2xl sm:max-w-md">
          {/* Header */}
          <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
            <div className="flex items-center gap-2">
              <Sparkles size={18} className="text-indigo-600" />
              <h2 className="text-sm font-semibold">Career assistant</h2>
            </div>
            <button
              onClick={() => setOpen(false)}
              className="text-slate-400 hover:text-slate-700"
            >
              <X size={20} />
            </button>
          </div>

          {/* Conversation */}
          <div ref={scrollRef} className="thin-scroll flex-1 space-y-4 overflow-y-auto p-4">
            {enabled === false && status && (
              <div className="flex items-start gap-2 rounded-lg bg-amber-50 p-3 text-xs text-amber-700">
                <AlertCircle size={14} className="mt-0.5 shrink-0" />
                <span>
                  No API key for <b>{status.labels[status.provider] ?? status.provider}</b>, the
                  selected assistant provider. Add its key on the backend, or pick a
                  different provider in <b>Settings → Assistant</b>.
                </span>
              </div>
            )}
            {messages.length === 0 && enabled !== false && (
              <div className="space-y-2 text-sm text-slate-500">
                <p>Ask about your pipeline — it can search your jobs, read descriptions, check stats, and compare a role to your resume.</p>
                <div className="flex flex-wrap gap-1.5">
                  {[
                    "Which saved jobs best fit my resume?",
                    "How many jobs am I tracking?",
                    "Summarize the remote roles I saved.",
                  ].map((s) => (
                    <button
                      key={s}
                      onClick={() => setInput(s)}
                      className="rounded-full border border-slate-200 px-2.5 py-1 text-xs text-slate-600 hover:bg-slate-50"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((m, i) =>
              m.role === "user" ? (
                <div key={i} className="flex justify-end">
                  <div className="max-w-[85%] rounded-2xl rounded-br-sm bg-indigo-600 px-3 py-2 text-sm text-white">
                    {m.content}
                  </div>
                </div>
              ) : (
                <div key={i} className="prose prose-sm max-w-none text-slate-700">
                  <Markdown>{m.content}</Markdown>
                </div>
              )
            )}

            {/* In-flight assistant turn */}
            {streaming && (
              <div className="space-y-2">
                {tools.map((t, i) => (
                  <div key={i} className="flex items-center gap-1.5 text-xs text-slate-400">
                    {t.done ? (
                      <Wrench size={12} className={t.error ? "text-rose-500" : "text-emerald-500"} />
                    ) : (
                      <Loader2 size={12} className="animate-spin text-indigo-500" />
                    )}
                    <span>{t.name.replace(/_/g, " ")}</span>
                  </div>
                ))}
                {draft ? (
                  <div className="prose prose-sm max-w-none text-slate-700">
                    <Markdown>{draft}</Markdown>
                  </div>
                ) : tools.length === 0 ? (
                  <Loader2 size={16} className="animate-spin text-indigo-500" />
                ) : null}
              </div>
            )}
          </div>

          {/* Composer */}
          <div className="border-t border-slate-200 p-3">
            <div className="flex items-end gap-2">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    send();
                  }
                }}
                rows={1}
                placeholder={enabled === false ? "Assistant disabled" : "Ask about your jobs…"}
                disabled={enabled === false || streaming}
                className="max-h-32 flex-1 resize-none rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-indigo-400 disabled:bg-slate-50"
              />
              <button
                onClick={send}
                disabled={!input.trim() || streaming || enabled === false}
                className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-indigo-600 text-white transition hover:bg-indigo-700 disabled:opacity-40"
              >
                {streaming ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
