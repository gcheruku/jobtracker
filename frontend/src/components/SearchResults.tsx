import { useQuery } from "@tanstack/react-query";
import { MapPin, Search } from "lucide-react";
import { api } from "../lib/api";
import { STATUS_STYLES, initials } from "../lib/ui";
import type { Job, JobFilters, PipelineStatus } from "../lib/types";

function statusLabel(job: Job): string {
  return job.ignored ? "Skipped" : job.status;
}

function MatchBadge({ job }: { job: Job }) {
  const pct = job.llm_match_pct ?? job.match_pct;
  if (pct == null) return null;
  const color =
    pct >= 75 ? "bg-emerald-100 text-emerald-700" : pct >= 40 ? "bg-amber-100 text-amber-700" : "bg-slate-100 text-slate-500";
  return <span className={`rounded-md px-1.5 py-0.5 text-[11px] font-semibold ${color}`}>{Math.round(pct)}%</span>;
}

/**
 * Global search across every job — active board, plus Rejected/Expired and
 * Skipped — so a query in the top bar finds inactive jobs too.
 */
export function SearchResults({
  filters,
  onOpen,
}: {
  filters: JobFilters;
  onOpen: (j: Job) => void;
}) {
  const results = useQuery({
    queryKey: ["jobs", "search", filters],
    queryFn: () => api.listJobs({ ...filters, include_ignored: true }),
  });

  const jobs = results.data ?? [];

  return (
    <div className="p-6">
      <div className="mb-4 flex items-center gap-2 text-slate-600">
        <Search size={18} className="text-indigo-600" />
        <h2 className="text-base font-semibold">
          {results.isLoading ? "Searching…" : `${jobs.length} result${jobs.length === 1 ? "" : "s"}`}
          {filters.q ? <span className="font-normal text-slate-400"> for “{filters.q}”</span> : null}
        </h2>
        <span className="ml-2 text-xs text-slate-400">across all statuses</span>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {jobs.map((job) => {
          const lbl = statusLabel(job);
          const style = STATUS_STYLES[lbl as PipelineStatus];
          return (
            <button
              key={job.job_key}
              onClick={() => onOpen(job)}
              className="flex flex-col rounded-lg border border-slate-200 bg-white p-3 text-left shadow-sm transition hover:shadow-md"
            >
              <div className="flex items-start gap-2">
                <div className="grid h-8 w-8 shrink-0 place-items-center rounded-md bg-slate-100 text-xs font-bold text-slate-600">
                  {initials(job.company)}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-semibold leading-tight">
                    {job.title || "Untitled role"}
                  </div>
                  <div className="truncate text-xs text-slate-500">
                    {job.company || "Unknown company"}
                  </div>
                </div>
                <span
                  className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${
                    style?.chip ?? "bg-slate-100 text-slate-600"
                  }`}
                >
                  {lbl}
                </span>
              </div>
              <div className="mt-2 flex items-center justify-between">
                <span className="flex items-center gap-1 truncate text-[11px] text-slate-400">
                  {job.location && <MapPin size={12} />}
                  {job.work_mode || job.location || ""}
                </span>
                <MatchBadge job={job} />
              </div>
              {job.salary && (
                <div className="mt-1 truncate text-[11px] font-medium text-emerald-600">
                  {job.salary}
                </div>
              )}
            </button>
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
