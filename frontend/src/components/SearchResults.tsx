import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, ExternalLink, Eye, EyeOff, MapPin, Minus, Search } from "lucide-react";
import { api } from "../lib/api";
import { STATUS_STYLES, initials } from "../lib/ui";
import { MatchBadge } from "./MatchBadge";
import { SourceTag } from "./SourceTag";
import type { Job, JobFilters, PipelineStatus } from "../lib/types";

function statusLabel(job: Job): string {
  return job.ignored ? "Skipped" : job.status;
}

/**
 * Global search across every job — active board, plus Rejected/Expired and
 * Skipped — so a query in the top bar finds inactive jobs too.
 */
export function SearchResults({
  filters,
  onOpen,
  onToggleSelect,
  onRangeSelect,
  onClearSelection,
  anchorKey,
  selectedKeys,
}: {
  filters: JobFilters;
  onOpen: (j: Job) => void;
  // Multi-select shares the board's selection state so the same bulk
  // status/skip action bar (rendered in App) operates on search results too.
  onToggleSelect: (j: Job) => void;
  onRangeSelect: (keys: string[]) => void;
  onClearSelection: () => void;
  anchorKey: string | null;
  selectedKeys: Set<string>;
}) {
  const qc = useQueryClient();
  const searchKey = ["jobs", "search", filters] as const;
  // Dashboard search is scoped to the active board only (Saved/Applied/
  // Interviewing/Offer). Skipped/Rejected/Expired are searched from the
  // Inactive screen instead.
  const results = useQuery({
    queryKey: searchKey,
    queryFn: () => api.listJobs({ ...filters, board_only: true }),
  });

  const refresh = () => {
    // Re-sync everything (incl. this search list) with server truth. The
    // optimistic onMutate gives instant feedback; this confirms/corrects it.
    qc.invalidateQueries({ queryKey: ["jobs"] });
    qc.invalidateQueries({ queryKey: ["stats"] });
    qc.invalidateQueries({ queryKey: ["activity"] });
  };

  // Optimistically flip the card's ignored flag so the chip/icon update instantly.
  const setIgnoredLocally = (jobKey: string, ignored: boolean) =>
    qc.setQueryData<Job[]>(searchKey, (old) =>
      old?.map((j) => (j.job_key === jobKey ? { ...j, ignored } : j))
    );

  const skip = useMutation({
    mutationFn: (k: string) => api.ignoreJob(k),
    onMutate: (k: string) => setIgnoredLocally(k, true),
    onSettled: refresh,
  });
  const restore = useMutation({
    mutationFn: (k: string) => api.restoreJob(k),
    onMutate: (k: string) => setIgnoredLocally(k, false),
    onSettled: refresh,
  });

  const jobs = results.data ?? [];
  const selectionMode = selectedKeys.size > 0;

  // Select-all state across the current result set.
  const selectedCount = jobs.reduce((n, j) => n + (selectedKeys.has(j.job_key) ? 1 : 0), 0);
  const allSelected = jobs.length > 0 && selectedCount === jobs.length;
  const someSelected = selectedCount > 0 && !allSelected;
  const toggleSelectAll = () =>
    allSelected ? onClearSelection() : onRangeSelect(jobs.map((j) => j.job_key));

  // Shift+click selects the contiguous range from the anchor to this card,
  // within the flat results order. Falls back to a single toggle otherwise.
  const handleSelect = (job: Job, shiftKey: boolean) => {
    if (shiftKey && anchorKey) {
      const ids = jobs.map((j) => j.job_key);
      const ai = ids.indexOf(anchorKey);
      const ti = ids.indexOf(job.job_key);
      if (ai !== -1 && ti !== -1) {
        const [lo, hi] = ai < ti ? [ai, ti] : [ti, ai];
        onRangeSelect(ids.slice(lo, hi + 1));
        return;
      }
    }
    onToggleSelect(job);
  };

  return (
    <div className="p-6">
      <div className="mb-4 flex flex-wrap items-center gap-2 text-slate-600">
        <Search size={18} className="text-indigo-600" />
        <h2 className="text-base font-semibold">
          {results.isLoading ? "Searching…" : `${jobs.length} result${jobs.length === 1 ? "" : "s"}`}
          {filters.q ? <span className="font-normal text-slate-400"> for “{filters.q}”</span> : null}
        </h2>
        <span className="ml-2 text-xs text-slate-400">
          on the board · search the Inactive tab for skipped/expired
        </span>
        {!results.isLoading && jobs.length > 0 && (
          <button
            onClick={toggleSelectAll}
            className="ml-auto inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-50"
          >
            <span
              className={`grid h-4 w-4 place-items-center rounded border ${
                allSelected
                  ? "border-indigo-600 bg-indigo-600 text-white"
                  : someSelected
                    ? "border-indigo-400 bg-indigo-100 text-indigo-600"
                    : "border-slate-300"
              }`}
            >
              {allSelected ? <Check size={12} /> : someSelected ? <Minus size={12} /> : null}
            </span>
            {allSelected ? "Deselect all" : "Select all"}
            {selectedCount > 0 && (
              <span className="text-xs font-normal text-slate-400">({selectedCount})</span>
            )}
          </button>
        )}
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {jobs.map((job) => {
          const lbl = statusLabel(job);
          const style = STATUS_STYLES[lbl as PipelineStatus];
          const selected = selectedKeys.has(job.job_key);
          return (
            <div
              key={job.job_key}
              onClick={(e) =>
                selectionMode || e.shiftKey ? handleSelect(job, e.shiftKey) : onOpen(job)
              }
              className={`group flex cursor-pointer select-none flex-col rounded-lg border bg-white p-3 text-left shadow-sm transition hover:shadow-md ${
                selected
                  ? "border-indigo-400 bg-indigo-50/50 ring-1 ring-indigo-300"
                  : "border-slate-200"
              }`}
            >
              <div className="flex items-start gap-2">
                {/* Avatar doubles as a select toggle (Gmail-style): tap to select. */}
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleSelect(job, e.shiftKey);
                  }}
                  title={selected ? "Deselect" : "Select"}
                  className={`grid h-8 w-8 shrink-0 cursor-pointer place-items-center rounded-md text-xs font-bold transition ${
                    selected ? "bg-indigo-600 text-white" : "bg-slate-100 text-slate-600"
                  }`}
                >
                  {selected ? <Check size={16} /> : initials(job.company)}
                </button>
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-semibold leading-tight">
                    {job.title || "Untitled role"}
                  </div>
                  <div className="truncate text-xs text-slate-500">
                    {job.company || "Unknown company"}
                  </div>
                </div>
                {job.url && (
                  <a
                    href={job.url}
                    target="_blank"
                    rel="noreferrer"
                    onClick={(e) => e.stopPropagation()}
                    title="Open job posting"
                    className="opacity-0 transition group-hover:opacity-100"
                  >
                    <ExternalLink size={15} className="text-slate-400 hover:text-indigo-600" />
                  </a>
                )}
                {job.ignored ? (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      restore.mutate(job.job_key);
                    }}
                    title="Restore this job"
                    className="opacity-0 transition group-hover:opacity-100"
                  >
                    <Eye size={15} className="text-slate-400 hover:text-emerald-600" />
                  </button>
                ) : (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      skip.mutate(job.job_key);
                    }}
                    title="Skip this job"
                    className="opacity-0 transition group-hover:opacity-100"
                  >
                    <EyeOff size={15} className="text-slate-400 hover:text-rose-500" />
                  </button>
                )}
                <span
                  className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${
                    style?.chip ?? "bg-slate-100 text-slate-600"
                  }`}
                >
                  {lbl}
                </span>
              </div>
              <div className="mt-2 flex items-center justify-between gap-1">
                <span className="flex items-center gap-1 truncate text-[11px] text-slate-400">
                  {job.location && <MapPin size={12} />}
                  {job.work_mode || job.location || ""}
                </span>
                <span className="flex shrink-0 items-center gap-1.5">
                  <SourceTag source={job.source} />
                  <MatchBadge job={job} />
                </span>
              </div>
              {job.salary && (
                <div className="mt-1 truncate text-[11px] font-medium text-emerald-600">
                  {job.salary}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {!results.isLoading && jobs.length === 0 && (
        <div className="grid h-48 place-items-center text-sm text-slate-400">
          No jobs match “{filters.q}”.
        </div>
      )}
    </div>
  );
}
