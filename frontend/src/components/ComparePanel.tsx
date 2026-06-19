import { useMutation } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Sparkles, Loader2, X, Check, Minus } from "lucide-react";
import { api } from "../lib/api";
import type { CompareResult, Job } from "../lib/types";

function ScoreDonut({ score }: { score: number }) {
  const r = 52;
  const c = 2 * Math.PI * r;
  const offset = c - (score / 100) * c;
  const color = score >= 75 ? "#10b981" : score >= 40 ? "#f59e0b" : "#ef4444";
  return (
    <div className="relative h-36 w-36">
      <svg className="h-36 w-36 -rotate-90" viewBox="0 0 120 120">
        <circle cx="60" cy="60" r={r} fill="none" stroke="#e2e8f0" strokeWidth="12" />
        <motion.circle
          cx="60"
          cy="60"
          r={r}
          fill="none"
          stroke={color}
          strokeWidth="12"
          strokeLinecap="round"
          strokeDasharray={c}
          initial={{ strokeDashoffset: c }}
          animate={{ strokeDashoffset: offset }}
          transition={{ duration: 0.9, ease: "easeOut" }}
        />
      </svg>
      <div className="absolute inset-0 grid place-items-center">
        <div className="text-center">
          <div className="text-3xl font-bold" style={{ color }}>
            {score}%
          </div>
          <div className="text-xs text-slate-400">match</div>
        </div>
      </div>
    </div>
  );
}

function Chips({ result }: { result: CompareResult }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {result.keyword_chips.map((chip) => (
        <span
          key={chip.label}
          className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium ${
            chip.matched
              ? "bg-emerald-50 text-emerald-700"
              : "bg-rose-50 text-rose-600"
          }`}
        >
          {chip.matched ? <Check size={12} /> : <Minus size={12} />}
          {chip.label}
        </span>
      ))}
    </div>
  );
}

export function ComparePanel({ job, onClose }: { job: Job; onClose: () => void }) {
  const compare = useMutation({
    mutationFn: () => api.compare(job.job_key),
  });

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="absolute inset-0 z-20 flex flex-col bg-white"
    >
      <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
        <div className="flex items-center gap-2">
          <Sparkles size={18} className="text-indigo-600" />
          <h3 className="text-lg font-semibold">AI Resume Fit</h3>
        </div>
        <button onClick={onClose} className="text-slate-400 hover:text-slate-700">
          <X size={20} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-5">
        {!compare.data && !compare.isPending && (
          <div className="grid h-full place-items-center text-center">
            <div>
              <p className="mb-4 max-w-xs text-sm text-slate-500">
                Compare your active resume against{" "}
                <span className="font-medium">{job.title}</span> to see your match
                score, keyword gaps, and tailored prep.
              </p>
              <button
                onClick={() => compare.mutate()}
                className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-indigo-700"
              >
                <Sparkles size={16} />
                Run analysis
              </button>
            </div>
          </div>
        )}

        {compare.isPending && (
          <div className="grid h-full place-items-center">
            <div className="flex flex-col items-center gap-3 text-slate-500">
              <Loader2 size={28} className="animate-spin text-indigo-600" />
              <span className="text-sm">Analyzing resume vs. job…</span>
            </div>
          </div>
        )}

        {compare.isError && (
          <div className="rounded-lg bg-rose-50 p-4 text-sm text-rose-700">
            {(compare.error as Error).message}
            <div className="mt-1 text-xs text-rose-500">
              Tip: save a resume first (Resume section) so there's text to compare.
            </div>
          </div>
        )}

        {compare.data && (
          <div className="space-y-6">
            <div className="flex flex-col items-center gap-3 sm:flex-row sm:items-center sm:gap-6">
              <ScoreDonut score={compare.data.match_score} />
              <div className="flex-1">
                <p className="text-sm text-slate-600">{compare.data.summary}</p>
                <span className="mt-2 inline-block rounded bg-slate-100 px-2 py-0.5 text-[11px] text-slate-500">
                  source: {compare.data.source}
                </span>
              </div>
            </div>

            <section>
              <h4 className="mb-2 text-sm font-semibold text-slate-700">
                Keyword match
              </h4>
              <Chips result={compare.data} />
            </section>

            <section>
              <h4 className="mb-2 text-sm font-semibold text-slate-700">
                Interview prep questions
              </h4>
              <ul className="space-y-2">
                {compare.data.interview_questions.map((q, i) => (
                  <li
                    key={i}
                    className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700"
                  >
                    {q}
                  </li>
                ))}
              </ul>
            </section>

            <section>
              <h4 className="mb-2 text-sm font-semibold text-slate-700">
                Resume optimization tips
              </h4>
              <ul className="space-y-1.5">
                {compare.data.resume_tips.map((t, i) => (
                  <li key={i} className="flex gap-2 text-sm text-slate-600">
                    <Sparkles size={14} className="mt-0.5 shrink-0 text-indigo-500" />
                    {t}
                  </li>
                ))}
              </ul>
            </section>

            <button
              onClick={() => compare.mutate()}
              className="text-xs font-medium text-indigo-600 hover:underline"
            >
              Re-run analysis
            </button>
          </div>
        )}
      </div>
    </motion.div>
  );
}
