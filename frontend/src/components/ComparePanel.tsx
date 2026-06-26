import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Sparkles, Loader2, X, RotateCcw, AlertTriangle } from "lucide-react";
import { api } from "../lib/api";
import { Markdown } from "./Markdown";
import type { CompareResult, Job } from "../lib/types";

function scoreColor(score: number) {
  return score >= 75
    ? "bg-emerald-100 text-emerald-700"
    : score >= 40
      ? "bg-amber-100 text-amber-700"
      : "bg-rose-100 text-rose-700";
}

function Report({ r }: { r: CompareResult }) {
  return (
    <div>
      {!r.used_job_description && (
        <div className="mb-4 flex gap-2 rounded-lg bg-amber-50 p-3 text-xs text-amber-700">
          <AlertTriangle size={14} className="mt-0.5 shrink-0" />
          No job description could be fetched for this posting (the link may require
          login), so the analysis is based on the title/company only and is limited.
        </div>
      )}
      <article className="prose prose-sm max-w-none prose-headings:font-semibold prose-headings:text-slate-800 prose-h2:text-base prose-h2:mt-5 prose-strong:text-slate-800 prose-li:my-0.5 prose-p:text-slate-600">
        <Markdown>{r.report_markdown}</Markdown>
      </article>
      <div className="mt-5 text-[11px] text-slate-400">
        {r.source === "gemini" ? `Analyzed by ${r.model}` : "Offline heuristic"} ·{" "}
        {new Date(r.created_at).toLocaleString()}
      </div>
    </div>
  );
}

export function ComparePanel({ job, onClose }: { job: Job; onClose: () => void }) {
  const qc = useQueryClient();
  const [model, setModel] = useState<string | undefined>(undefined);

  const models = useQuery({ queryKey: ["ai-models"], queryFn: api.aiModels });
  const saved = useQuery({
    queryKey: ["compare", job.job_key],
    queryFn: () => api.getCompare(job.job_key),
  });

  useEffect(() => {
    if (model === undefined && models.data?.default) setModel(models.data.default);
  }, [models.data, model]);

  const run = useMutation({
    mutationFn: (force: boolean) => api.runCompare(job.job_key, { force, model }),
    onSuccess: (data) => {
      qc.setQueryData(["compare", job.job_key], data);
      qc.invalidateQueries({ queryKey: ["jobs"] }); // card picks up the new score
    },
  });

  const result = saved.data ?? null;
  const busy = run.isPending;

  const ModelPicker = models.data?.enabled ? (
    <select
      value={model ?? ""}
      onChange={(e) => setModel(e.target.value)}
      disabled={busy}
      className="rounded-md border border-slate-200 bg-white px-2 py-1 text-xs text-slate-600"
    >
      {models.data.models.map((m) => (
        <option key={m} value={m}>{m}</option>
      ))}
    </select>
  ) : null;

  return (
    <motion.div
      initial={{ opacity: 0 }} animate={{ opacity: 1 }}
      className="absolute inset-0 z-20 flex flex-col bg-white"
    >
      <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
        <div className="flex items-center gap-2">
          <Sparkles size={18} className="text-indigo-600" />
          <h3 className="text-lg font-semibold">AI Resume Fit</h3>
          {result && (
            <span
              className={`ml-1 rounded-md px-2 py-0.5 text-sm font-bold ${scoreColor(result.match_score)}`}
            >
              {result.match_score}%
            </span>
          )}
        </div>
        <button onClick={onClose} className="text-slate-400 hover:text-slate-700">
          <X size={20} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-5">
        {saved.isLoading ? (
          <div className="grid h-full place-items-center text-slate-400">
            <Loader2 size={24} className="animate-spin" />
          </div>
        ) : busy ? (
          <div className="grid h-full place-items-center">
            <div className="flex flex-col items-center gap-3 text-slate-500">
              <Loader2 size={28} className="animate-spin text-indigo-600" />
              <span className="text-sm">Fetching job description & analyzing…</span>
              <span className="text-xs text-slate-400">{model}</span>
            </div>
          </div>
        ) : result ? (
          <Report r={result} />
        ) : (
          <div className="grid h-full place-items-center text-center">
            <div>
              <p className="mb-4 max-w-xs text-sm text-slate-500">
                Get a detailed ATS-style analysis of your resume against{" "}
                <span className="font-medium">{job.title}</span>: match score, skill
                alignment, gaps & red flags, and rewritten bullet points.
              </p>
              {ModelPicker && <div className="mb-3 flex justify-center">{ModelPicker}</div>}
              <button
                onClick={() => run.mutate(false)}
                className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-indigo-700"
              >
                <Sparkles size={16} /> Run analysis
              </button>
            </div>
          </div>
        )}

        {run.isError && (
          <div className="mt-4 rounded-lg bg-rose-50 p-3 text-sm text-rose-700">
            {(run.error as Error).message}
          </div>
        )}
      </div>

      {result && !busy && (
        <div className="flex items-center justify-between gap-3 border-t border-slate-200 px-5 py-3">
          {ModelPicker ?? <span />}
          <button
            onClick={() => run.mutate(true)}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50"
          >
            <RotateCcw size={13} /> Re-run analysis
          </button>
        </div>
      )}
    </motion.div>
  );
}
