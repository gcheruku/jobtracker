import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RefreshCw, Loader2, Check, AlertCircle } from "lucide-react";
import { api } from "../lib/api";

/**
 * Triggers a Gmail job-alert fetch and polls /api/ingest/status until it
 * finishes, then refreshes the board. Also reflects scheduled runs in progress.
 */
export function FetchAlertsButton() {
  const qc = useQueryClient();
  const [polling, setPolling] = useState(false);
  const [flash, setFlash] = useState<string | null>(null);

  const statusQ = useQuery({
    queryKey: ["ingest-status"],
    queryFn: api.ingestStatus,
    refetchInterval: polling ? 2000 : false,
  });

  const start = useMutation({
    mutationFn: api.ingestRun,
    onSuccess: (r) => {
      if (r.started === false) setFlash(r.detail ?? "Already running");
      setPolling(true);
    },
  });

  // When a run we were polling finishes, refresh data and show a summary.
  useEffect(() => {
    if (polling && statusQ.data && !statusQ.data.running) {
      setPolling(false);
      const s = statusQ.data.last_summary;
      if (statusQ.data.last_error) setFlash(`Error: ${statusQ.data.last_error}`);
      else if (s) setFlash(`+${s.new_jobs} new · ${s.duplicates} dupes`);
      qc.invalidateQueries({ queryKey: ["jobs"] });
      qc.invalidateQueries({ queryKey: ["stats"] });
      qc.invalidateQueries({ queryKey: ["activity"] });
    }
  }, [polling, statusQ.data, qc]);

  useEffect(() => {
    if (!flash) return;
    const t = setTimeout(() => setFlash(null), 6000);
    return () => clearTimeout(t);
  }, [flash]);

  const running = polling || statusQ.data?.running || start.isPending;

  return (
    <div className="flex items-center gap-2">
      <button
        onClick={() => start.mutate()}
        disabled={running}
        title="Fetch the latest job alerts from Gmail"
        className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-indigo-700 disabled:opacity-60"
      >
        {running ? (
          <Loader2 size={15} className="animate-spin" />
        ) : (
          <RefreshCw size={15} />
        )}
        {running ? "Fetching…" : "Fetch alerts"}
      </button>
      {flash && (
        <span
          className={`inline-flex items-center gap-1 text-xs ${
            flash.startsWith("Error") ? "text-rose-600" : "text-emerald-600"
          }`}
        >
          {flash.startsWith("Error") ? <AlertCircle size={13} /> : <Check size={13} />}
          {flash}
        </span>
      )}
    </div>
  );
}
