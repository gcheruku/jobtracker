import { Sparkles } from "lucide-react";
import type { Job } from "../lib/types";

/**
 * Match badge on a job card. Priority: the detailed "Compare with Resume" score
 * (✦ sparkle + indigo ring), else the offline semantic score (≈ prefix), else
 * the initial ingestion score (plain). Each has a distinct tooltip.
 */
export function MatchBadge({ job }: { job: Job }) {
  let pct: number | null = null;
  let kind: "compare" | "semantic" | "initial" = "initial";

  if (job.compare_score != null) {
    pct = job.compare_score;
    kind = "compare";
  } else if (job.semantic_score != null) {
    pct = job.semantic_score;
    kind = "semantic";
  } else {
    pct = job.llm_match_pct ?? job.match_pct;
  }
  if (pct == null) return null;

  const color =
    pct >= 75
      ? "bg-emerald-100 text-emerald-700"
      : pct >= 40
        ? "bg-amber-100 text-amber-700"
        : "bg-slate-100 text-slate-500";

  const title =
    kind === "compare"
      ? "AI fit score (Compare with Resume)"
      : kind === "semantic"
        ? "Semantic match (offline)"
        : "Initial match score";

  return (
    <span
      title={title}
      className={`inline-flex items-center gap-0.5 rounded-md px-1.5 py-0.5 text-[11px] font-semibold ${color} ${
        kind === "compare" ? "ring-1 ring-indigo-400" : ""
      }`}
    >
      {kind === "compare" && <Sparkles size={10} className="text-indigo-500" />}
      {kind === "semantic" && <span className="text-violet-500">≈</span>}
      {Math.round(pct)}%
    </span>
  );
}
