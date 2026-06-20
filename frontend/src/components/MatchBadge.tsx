import { Sparkles } from "lucide-react";
import type { Job } from "../lib/types";

/**
 * Match badge on a job card. If a detailed "Compare with Resume" analysis exists,
 * its score replaces the initial ingestion score and is marked with a sparkle +
 * indigo ring so it's distinguishable from the initial estimate.
 */
export function MatchBadge({ job }: { job: Job }) {
  const initial = job.llm_match_pct ?? job.match_pct;
  const isCompare = job.compare_score != null;
  const pct = isCompare ? job.compare_score : initial;
  if (pct == null) return null;

  const color =
    pct >= 75
      ? "bg-emerald-100 text-emerald-700"
      : pct >= 40
        ? "bg-amber-100 text-amber-700"
        : "bg-slate-100 text-slate-500";

  return (
    <span
      title={isCompare ? "AI fit score (Compare with Resume)" : "Initial match score"}
      className={`inline-flex items-center gap-0.5 rounded-md px-1.5 py-0.5 text-[11px] font-semibold ${color} ${
        isCompare ? "ring-1 ring-indigo-400" : ""
      }`}
    >
      {isCompare && <Sparkles size={10} className="text-indigo-500" />}
      {Math.round(pct)}%
    </span>
  );
}
