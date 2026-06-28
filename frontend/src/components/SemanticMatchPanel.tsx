import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Cpu, Loader2, Play, Check } from "lucide-react";
import { api } from "../lib/api";

/**
 * Scores Saved jobs (no match score yet) against the resume using embeddings —
 * Gemini by default, or the offline sentence-transformers model in WITH_SEMANTIC
 * builds — pulling each job description via its link. New jobs are scored at
 * ingest; this backfills existing ones. Shows live progress until finished.
 */
export function SemanticMatchPanel() {
  const qc = useQueryClient();
  const [polling, setPolling] = useState(false);

  const statusQ = useQuery({
    queryKey: ["semantic-status"],
    queryFn: () => api.semanticStatus(true), // Saved-jobs scope
    refetchInterval: polling ? 1500 : false,
  });

  const run = useMutation({
    mutationFn: (recheck: boolean) => api.runSemantic(recheck, true),
    onSuccess: () => setPolling(true),
  });

  const s = statusQ.data;
  const running = polling || s?.running;

  useEffect(() => {
    if (polling && s && !s.running) {
      setPolling(false);
      qc.invalidateQueries({ queryKey: ["jobs"] });
    }
  }, [polling, s, qc]);

  const pct = s && s.total > 0 ? Math.round((s.done / s.total) * 100) : 0;

  return (
    <div className="mt-6 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-2 flex items-center gap-2">
        <Cpu size={18} className="text-indigo-600" />
        <h3 className="text-sm font-semibold">Semantic matching (Saved jobs)</h3>
      </div>
      <p className="mb-4 text-sm text-slate-500">
        Computes a résumé↔job-description similarity score for <b>Saved</b> jobs
        that don't already have one — pulling each job description from its link.
        Then sort the board by <b>Semantic match</b> to triage. New jobs are scored
        automatically at ingest.
      </p>

      {s && !s.available && (
        <div className="rounded-lg bg-amber-50 p-3 text-xs text-amber-700">
          No embedding backend is available on the server — set{" "}
          <code>GOOGLE_API_KEY</code> (Gemini embeddings), or build with{" "}
          <code>WITH_SEMANTIC=true</code> for the offline model.
        </div>
      )}

      {running ? (
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-sm text-slate-600">
            <Loader2 size={15} className="animate-spin text-indigo-600" />
            Scoring {s?.done ?? 0} / {s?.total ?? 0} · {s?.scored ?? 0} scored ·{" "}
            {s?.expired ?? 0} expired · {s?.no_jd ?? 0} no description
          </div>
          <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
            <div
              className="h-full bg-indigo-500 transition-all"
              style={{ width: `${pct}%` }}
            />
          </div>
          <p className="text-xs text-slate-400">
            First run loads the model; pulling job descriptions takes a moment each.
          </p>
        </div>
      ) : (
        <div className="flex flex-wrap items-center gap-3">
          <button
            onClick={() => run.mutate(false)}
            disabled={!s?.available || (s?.eligible ?? 0) === 0}
            className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50"
          >
            <Play size={15} /> Score Saved jobs
          </button>
          <button
            onClick={() => run.mutate(true)}
            disabled={!s?.available}
            title="Re-check Saved jobs (incl. already-attempted), moving expired postings off the board"
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 px-3 py-2 text-xs font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-50"
          >
            Re-check / expired
          </button>
          <span className="text-xs text-slate-500">
            {s?.eligible ?? 0} Saved job{(s?.eligible ?? 0) === 1 ? "" : "s"} to score
          </span>
          {s?.last_run_iso && !s.last_error && (s?.eligible ?? 0) >= 0 && (
            <span className="inline-flex items-center gap-1 text-xs text-emerald-600">
              <Check size={13} /> last run scored {s.scored}
              {s.expired ? ` · ${s.expired} expired` : ""}
              {s.no_jd ? ` · ${s.no_jd} no description` : ""}
            </span>
          )}
        </div>
      )}

      {s?.last_error && (
        <div className="mt-2 text-xs text-rose-600">Error: {s.last_error}</div>
      )}
    </div>
  );
}
