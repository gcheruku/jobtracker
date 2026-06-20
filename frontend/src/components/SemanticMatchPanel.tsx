import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Cpu, Loader2, Play, Check } from "lucide-react";
import { api } from "../lib/api";

/**
 * Runs the offline semantic (sentence-transformers) match on active-board jobs
 * that have no match score, pulling each job description via its link. Shows
 * live progress until finished. Inactive jobs are not scored.
 */
export function SemanticMatchPanel() {
  const qc = useQueryClient();
  const [polling, setPolling] = useState(false);

  const statusQ = useQuery({
    queryKey: ["semantic-status"],
    queryFn: api.semanticStatus,
    refetchInterval: polling ? 1500 : false,
  });

  const run = useMutation({
    mutationFn: api.runSemantic,
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
        <h3 className="text-sm font-semibold">Offline semantic matching</h3>
      </div>
      <p className="mb-4 text-sm text-slate-500">
        Computes a resume↔job-description similarity (sentence-transformers) for
        active jobs that don't already have a match score — pulling each job
        description from its link. Inactive jobs are skipped.
      </p>

      {s && !s.available && (
        <div className="rounded-lg bg-amber-50 p-3 text-xs text-amber-700">
          The semantic model isn't installed on the server
          (<code>pip install sentence-transformers</code>).
        </div>
      )}

      {running ? (
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-sm text-slate-600">
            <Loader2 size={15} className="animate-spin text-indigo-600" />
            Scoring {s?.done ?? 0} / {s?.total ?? 0} · {s?.scored ?? 0} scored ·{" "}
            {s?.no_jd ?? 0} no description
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
        <div className="flex items-center gap-3">
          <button
            onClick={() => run.mutate()}
            disabled={!s?.available || (s?.eligible ?? 0) === 0}
            className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50"
          >
            <Play size={15} /> Run semantic matching
          </button>
          <span className="text-xs text-slate-500">
            {s?.eligible ?? 0} job{(s?.eligible ?? 0) === 1 ? "" : "s"} to score
          </span>
          {s?.last_run_iso && !s.last_error && (s?.eligible ?? 0) >= 0 && (
            <span className="inline-flex items-center gap-1 text-xs text-emerald-600">
              <Check size={13} /> last run scored {s.scored}
              {s.no_jd ? ` · ${s.no_jd} had no description` : ""}
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
