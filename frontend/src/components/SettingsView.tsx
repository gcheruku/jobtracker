import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Save, RefreshCw, Check, AlertCircle, SlidersHorizontal, Sparkles } from "lucide-react";
import { api } from "../lib/api";
import { agentStatus } from "../lib/agent";
import { SemanticMatchPanel } from "./SemanticMatchPanel";
import type { Settings } from "../lib/types";

const EMPTY: Settings = {
  city: "",
  max_distance_miles: null,
  salary_min: null,
  salary_max: null,
  min_match_score: null,
  title_keywords: [],
  exclude_companies: [],
  agent_provider: null,
};

const numOrNull = (v: string) => (v.trim() === "" ? null : Number(v));
const csv = (v: string) => v.split(",").map((x) => x.trim()).filter(Boolean);

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="text-sm font-medium text-slate-700">{label}</span>
      {hint && <span className="ml-2 text-xs text-slate-400">{hint}</span>}
      <div className="mt-1">{children}</div>
    </label>
  );
}

const inputCls =
  "w-full rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-indigo-400";

export function SettingsView() {
  const qc = useQueryClient();
  const saved = useQuery({ queryKey: ["settings"], queryFn: api.getSettings });
  const [form, setForm] = useState<Settings>(EMPTY);
  const [phase, setPhase] = useState<"idle" | "ask" | "applying" | "done">("idle");
  const [polling, setPolling] = useState(false);

  useEffect(() => {
    if (saved.data) setForm(saved.data);
  }, [saved.data]);

  const save = useMutation({
    mutationFn: (s: Settings) => api.saveSettings(s),
    onSuccess: (s) => {
      qc.setQueryData(["settings"], s);
      setPhase("ask"); // prompt to reset the board
    },
  });

  const statusQ = useQuery({
    queryKey: ["apply-status"],
    queryFn: api.applyStatus,
    refetchInterval: polling ? 1500 : false,
  });

  const startApply = useMutation({
    mutationFn: api.applySettings,
    onSuccess: () => {
      setPolling(true);
      setPhase("applying");
    },
  });

  useEffect(() => {
    if (polling && statusQ.data && !statusQ.data.running) {
      setPolling(false);
      setPhase("done");
      qc.invalidateQueries({ queryKey: ["jobs"] });
      qc.invalidateQueries({ queryKey: ["stats"] });
    }
  }, [polling, statusQ.data, qc]);

  const set = (patch: Partial<Settings>) => {
    setForm((f) => ({ ...f, ...patch }));
    if (phase !== "idle") setPhase("idle");
  };

  // Assistant provider: its own query + save so changing it doesn't trigger the
  // "reset the board" prompt that the job-preferences save does.
  const agentQ = useQuery({ queryKey: ["agent-status"], queryFn: agentStatus });
  const saveProvider = useMutation({
    mutationFn: (s: Settings) => api.saveSettings(s),
    onSuccess: (s) => {
      qc.setQueryData(["settings"], s);
      qc.invalidateQueries({ queryKey: ["agent-status"] });
    },
  });
  const provider = form.agent_provider ?? agentQ.data?.provider ?? "anthropic";
  const providerHasKey = agentQ.data?.providers?.[provider] ?? true;

  const summary = statusQ.data?.last_summary;

  return (
    <div className="mx-auto max-w-2xl p-6">
      <div className="mb-5 flex items-center gap-2">
        <SlidersHorizontal size={18} className="text-indigo-600" />
        <h2 className="text-lg font-semibold">Job preferences</h2>
      </div>
      <p className="mb-5 text-sm text-slate-500">
        Set what you're looking for. Jobs that clearly don't match are moved to the{" "}
        <span className="font-medium">Mismatched</span> list (Inactive tab); jobs with
        unknown salary/location stay on the board. Distance is ignored for remote jobs.
      </p>

      <div className="space-y-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <Field label="Home city" hint="for distance, e.g. Irving, TX">
          <input
            className={inputCls}
            value={form.city}
            onChange={(e) => set({ city: e.target.value })}
            placeholder="Irving, TX"
          />
        </Field>

        <div className="grid grid-cols-2 gap-4">
          <Field label="Max distance" hint="miles (non-remote)">
            <input
              type="number"
              className={inputCls}
              value={form.max_distance_miles ?? ""}
              onChange={(e) => set({ max_distance_miles: numOrNull(e.target.value) })}
              placeholder="30"
            />
          </Field>
          <Field label="Min match score" hint="0-100">
            <input
              type="number"
              className={inputCls}
              value={form.min_match_score ?? ""}
              onChange={(e) => set({ min_match_score: numOrNull(e.target.value) })}
              placeholder="e.g. 60"
            />
          </Field>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <Field label="Min salary" hint="annual $">
            <input
              type="number"
              className={inputCls}
              value={form.salary_min ?? ""}
              onChange={(e) => set({ salary_min: numOrNull(e.target.value) })}
              placeholder="120000"
            />
          </Field>
          <Field label="Max salary" hint="annual $ (optional)">
            <input
              type="number"
              className={inputCls}
              value={form.salary_max ?? ""}
              onChange={(e) => set({ salary_max: numOrNull(e.target.value) })}
              placeholder=""
            />
          </Field>
        </div>

        <Field label="Title keywords" hint="comma-separated; keep jobs whose title has any">
          <input
            className={inputCls}
            value={form.title_keywords.join(", ")}
            onChange={(e) => set({ title_keywords: csv(e.target.value) })}
            placeholder="engineer, manager, architect"
          />
        </Field>

        <Field label="Exclude companies" hint="comma-separated">
          <input
            className={inputCls}
            value={form.exclude_companies.join(", ")}
            onChange={(e) => set({ exclude_companies: csv(e.target.value) })}
            placeholder="Acme, Globex"
          />
        </Field>

        <div className="flex items-center gap-3 pt-1">
          <button
            onClick={() => save.mutate(form)}
            disabled={save.isPending}
            className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-60"
          >
            {save.isPending ? <Loader2 size={15} className="animate-spin" /> : <Save size={15} />}
            Save preferences
          </button>
          {save.isError && (
            <span className="text-xs text-rose-600">{(save.error as Error).message}</span>
          )}
        </div>
      </div>

      {/* Apply / reset-board prompt */}
      {phase === "ask" && (
        <div className="mt-4 rounded-xl border border-indigo-200 bg-indigo-50 p-4">
          <p className="text-sm text-indigo-800">
            Preferences saved. Reset the board to match? This moves non-matching jobs
            into the <span className="font-medium">Mismatched</span> list and brings back
            any that now match. (First run may take a minute while it looks up locations.)
          </p>
          <div className="mt-3 flex gap-2">
            <button
              onClick={() => startApply.mutate()}
              className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-indigo-700"
            >
              <RefreshCw size={14} /> Reset board now
            </button>
            <button
              onClick={() => setPhase("idle")}
              className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-600 hover:bg-white"
            >
              Not now
            </button>
          </div>
        </div>
      )}

      {phase === "applying" && (
        <div className="mt-4 flex items-center gap-2 rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-600">
          <Loader2 size={16} className="animate-spin text-indigo-600" />
          Applying preferences and resetting the board…
        </div>
      )}

      {phase === "done" && summary && (
        <div className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">
          <div className="flex items-center gap-2 font-medium">
            <Check size={16} /> Board updated
          </div>
          <ul className="mt-1 list-inside list-disc">
            <li>{summary.moved_to_mismatched} moved to Mismatched</li>
            <li>{summary.restored} brought back to the board</li>
            <li>{summary.evaluated} jobs evaluated</li>
          </ul>
          {summary.geocode_failures > 0 && (
            <div className="mt-1 flex items-center gap-1 text-amber-700">
              <AlertCircle size={13} /> Couldn't geocode your city — distance was skipped.
            </div>
          )}
        </div>
      )}

      {/* Career assistant provider */}
      <div className="mt-8 rounded-xl border border-slate-200 bg-white p-5">
        <div className="mb-1 flex items-center gap-2">
          <Sparkles size={18} className="text-indigo-600" />
          <h2 className="text-lg font-semibold">Career assistant</h2>
        </div>
        <p className="mb-4 text-sm text-slate-500">
          Choose which AI provider powers the chat assistant. Each needs its own API
          key configured on the backend.
        </p>
        <Field label="Provider">
          <select
            value={provider}
            onChange={(e) => {
              const next = { ...form, agent_provider: e.target.value };
              setForm(next);
              saveProvider.mutate(next);
            }}
            className={inputCls + " cursor-pointer"}
          >
            {(["anthropic", "gemini", "openai"] as const).map((p) => {
              const label = agentQ.data?.labels?.[p] ?? p;
              const hasKey = agentQ.data?.providers?.[p];
              return (
                <option key={p} value={p}>
                  {label}
                  {hasKey === false ? " — no key" : ""}
                </option>
              );
            })}
          </select>
        </Field>
        <div className="mt-2 min-h-[1.25rem] text-xs">
          {saveProvider.isPending ? (
            <span className="text-slate-400">Saving…</span>
          ) : providerHasKey ? (
            <span className="inline-flex items-center gap-1 text-emerald-600">
              <Check size={13} /> Key configured for{" "}
              {agentQ.data?.labels?.[provider] ?? provider}.
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 text-amber-600">
              <AlertCircle size={13} /> No API key set for{" "}
              {agentQ.data?.labels?.[provider] ?? provider} — the assistant won't work
              until you add it on the backend.
            </span>
          )}
        </div>
      </div>

      <SemanticMatchPanel />
    </div>
  );
}
