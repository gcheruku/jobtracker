import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  RefreshCw,
  Loader2,
  Check,
  AlertCircle,
  AlertTriangle,
  ChevronDown,
  CalendarClock,
  Database,
  X,
} from "lucide-react";
import { api } from "../lib/api";
import { Toast } from "./Toast";

type Panel = "menu" | "since" | "confirm";
type RunOpts = { since_epoch?: number; fetch_all?: boolean } | undefined;

/**
 * Triggers a Gmail job-alert fetch (incremental, since a date, or full) and
 * polls /api/ingest/status until it finishes. Progress and the result are shown
 * in a bottom toast rather than inline next to the button.
 */
export function FetchAlertsButton() {
  const qc = useQueryClient();
  const [polling, setPolling] = useState(false);
  const [flash, setFlash] = useState<{ kind: "ok" | "err"; text: string } | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [panel, setPanel] = useState<Panel>("menu");
  const [since, setSince] = useState("");
  // Lets the user hide the toast while a fetch keeps running in the background.
  const [toastHidden, setToastHidden] = useState(false);
  const groupRef = useRef<HTMLDivElement>(null);

  const statusQ = useQuery({
    queryKey: ["ingest-status"],
    queryFn: api.ingestStatus,
    refetchInterval: polling ? 2000 : false,
  });

  const start = useMutation({
    mutationFn: (opts: RunOpts) => api.ingestRun(opts),
    onSuccess: (r) => {
      if (r.started === false) setFlash({ kind: "err", text: r.detail ?? "Already running" });
      else setFlash(null);
      setPolling(true);
    },
  });

  // When a run we were polling finishes, refresh data and show a summary.
  useEffect(() => {
    if (polling && statusQ.data && !statusQ.data.running) {
      setPolling(false);
      const s = statusQ.data.last_summary;
      setToastHidden(false); // surface the result even if the spinner was hidden
      if (statusQ.data.last_error)
        setFlash({ kind: "err", text: `Error: ${statusQ.data.last_error}` });
      else if (s)
        setFlash({ kind: "ok", text: `+${s.new_jobs} new · ${s.duplicates} duplicates` });
      qc.invalidateQueries({ queryKey: ["jobs"] });
      qc.invalidateQueries({ queryKey: ["stats"] });
      qc.invalidateQueries({ queryKey: ["activity"] });
    }
  }, [polling, statusQ.data, qc]);

  // Auto-dismiss the result toast (but never the in-progress one).
  useEffect(() => {
    if (!flash) return;
    const t = setTimeout(() => setFlash(null), 7000);
    return () => clearTimeout(t);
  }, [flash]);

  const running = polling || statusQ.data?.running || start.isPending;

  const openMenu = () => {
    setPanel("menu");
    setMenuOpen(true);
  };
  const closeMenu = () => setMenuOpen(false);

  function run(opts: RunOpts) {
    setToastHidden(false);
    start.mutate(opts);
    closeMenu();
  }
  function runSince() {
    if (!since) return;
    const epoch = Math.floor(new Date(`${since}T00:00:00`).getTime() / 1000);
    run({ since_epoch: epoch });
  }

  const anchor = groupRef.current?.getBoundingClientRect() ?? null;
  const menuStyle = anchor
    ? { top: anchor.bottom + 8, right: Math.max(8, window.innerWidth - anchor.right) }
    : undefined;

  return (
    <>
      {/* Split button: primary action + options caret */}
      <div ref={groupRef} className="inline-flex">
        <button
          onClick={() => run(undefined)}
          disabled={running}
          title="Fetch the latest job alerts from Gmail"
          className="inline-flex items-center gap-1.5 rounded-l-lg bg-indigo-600 px-3 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-indigo-700 disabled:opacity-60"
        >
          {running ? <Loader2 size={15} className="animate-spin" /> : <RefreshCw size={15} />}
          <span className="hidden sm:inline">{running ? "Fetching…" : "Fetch alerts"}</span>
        </button>
        <button
          onClick={openMenu}
          disabled={running}
          title="Fetch options"
          className="grid place-items-center rounded-r-lg border-l border-indigo-500 bg-indigo-600 px-2 text-white transition hover:bg-indigo-700 disabled:opacity-60"
        >
          <ChevronDown size={16} />
        </button>
      </div>

      {/* Options menu (portaled to escape the top bar's backdrop-filter) */}
      {menuOpen &&
        createPortal(
          <>
            <div className="fixed inset-0 z-50" onClick={closeMenu} />
            <div
              style={menuStyle}
              className="fixed z-50 w-72 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-2xl"
            >
              {panel === "menu" && (
                <div className="py-1">
                  <MenuItem
                    icon={<RefreshCw size={15} className="text-indigo-600" />}
                    title="Fetch new alerts"
                    desc="Only emails newer than the last fetch"
                    onClick={() => run(undefined)}
                  />
                  <MenuItem
                    icon={<CalendarClock size={15} className="text-indigo-600" />}
                    title="Fetch since a date…"
                    desc="Re-scan emails from a chosen start date"
                    onClick={() => setPanel("since")}
                  />
                  <MenuItem
                    icon={<Database size={15} className="text-indigo-600" />}
                    title="Fetch everything"
                    desc="Scan the entire Job alerts label"
                    onClick={() => setPanel("confirm")}
                  />
                </div>
              )}

              {panel === "since" && (
                <div className="p-3">
                  <div className="mb-2 text-sm font-semibold">Fetch alerts since</div>
                  <input
                    type="date"
                    value={since}
                    max={new Date().toISOString().slice(0, 10)}
                    onChange={(e) => setSince(e.target.value)}
                    className="mb-3 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-indigo-400"
                  />
                  <div className="flex gap-2">
                    <button
                      onClick={() => setPanel("menu")}
                      className="flex-1 rounded-lg border border-slate-200 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50"
                    >
                      Back
                    </button>
                    <button
                      onClick={runSince}
                      disabled={!since}
                      className="flex-1 rounded-lg bg-indigo-600 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50"
                    >
                      Fetch
                    </button>
                  </div>
                </div>
              )}

              {panel === "confirm" && (
                <div className="p-3">
                  <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-amber-700">
                    <AlertTriangle size={16} /> Fetch everything?
                  </div>
                  <p className="mb-3 text-xs leading-relaxed text-slate-600">
                    This scans your entire <b>Job alerts</b> label, ignoring the last-fetch
                    marker. It can take several minutes and use more Gemini quota. Already-saved
                    jobs are skipped, so nothing is duplicated.
                  </p>
                  <div className="flex gap-2">
                    <button
                      onClick={() => setPanel("menu")}
                      className="flex-1 rounded-lg border border-slate-200 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={() => run({ fetch_all: true })}
                      className="flex-1 rounded-lg bg-amber-600 py-2 text-sm font-semibold text-white hover:bg-amber-700"
                    >
                      Fetch all
                    </button>
                  </div>
                </div>
              )}
            </div>
          </>,
          document.body
        )}

      {/* In-progress + result toast */}
      <Toast open={(!!running || !!flash) && !toastHidden}>
        <div className="rounded-xl border border-slate-200 bg-white p-3 shadow-2xl">
          {running ? (
            <div className="flex items-center gap-3">
              <Loader2 size={20} className="shrink-0 animate-spin text-indigo-600" />
              <div className="min-w-0 flex-1">
                <div className="text-sm font-semibold">Fetching alerts…</div>
                <div className="text-xs text-slate-500">
                  This can take a few minutes. You can keep working.
                </div>
              </div>
              <button
                onClick={() => setToastHidden(true)}
                title="Hide (fetch keeps running)"
                className="shrink-0 text-slate-400 hover:text-slate-700"
              >
                <X size={16} />
              </button>
            </div>
          ) : flash ? (
            <div className="flex items-start gap-3">
              {flash.kind === "err" ? (
                <AlertCircle size={18} className="mt-0.5 shrink-0 text-rose-500" />
              ) : (
                <Check size={18} className="mt-0.5 shrink-0 text-emerald-500" />
              )}
              <div className="min-w-0 flex-1">
                <div className="text-sm font-semibold">
                  {flash.kind === "err" ? "Fetch failed" : "Fetch complete"}
                </div>
                <div className="truncate text-xs text-slate-500">{flash.text}</div>
              </div>
              <button
                onClick={() => setFlash(null)}
                className="text-slate-400 hover:text-slate-700"
              >
                <X size={16} />
              </button>
            </div>
          ) : null}
        </div>
      </Toast>
    </>
  );
}

function MenuItem({
  icon,
  title,
  desc,
  onClick,
}: {
  icon: React.ReactNode;
  title: string;
  desc: string;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="flex w-full items-start gap-2.5 px-3 py-2.5 text-left hover:bg-slate-50"
    >
      <span className="mt-0.5">{icon}</span>
      <span className="min-w-0">
        <span className="block text-sm font-medium text-slate-700">{title}</span>
        <span className="block text-xs text-slate-400">{desc}</span>
      </span>
    </button>
  );
}
