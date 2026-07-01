import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ExternalLink, MapPin, Star } from "lucide-react";
import { api } from "../lib/api";
import { STATUS_STYLES, initials } from "../lib/ui";
import { MatchBadge } from "./MatchBadge";
import { SourceTag } from "./SourceTag";
import type { Job, PipelineStatus } from "../lib/types";

/**
 * Jobs starred for later revisit (e.g. blocked on securing a referral).
 * Orthogonal to the pipeline — each card shows its current status; the "why"
 * lives in the job's notes. Unstar here to remove from the list.
 */
export function WatchlistView({ onOpen }: { onOpen: (j: Job) => void }) {
  const qc = useQueryClient();
  const listKey = ["jobs", "watchlist"] as const;
  const results = useQuery({
    queryKey: listKey,
    queryFn: () => api.listJobs({ watchlist: true }),
  });

  const unstar = useMutation({
    mutationFn: (k: string) => api.setWatchlist(k, false),
    // Optimistically drop the card so the list feels instant.
    onMutate: (k: string) =>
      qc.setQueryData<Job[]>(listKey, (old) => old?.filter((j) => j.job_key !== k)),
    onSettled: () => {
      qc.invalidateQueries({ queryKey: ["jobs"] });
      qc.invalidateQueries({ queryKey: ["stats"] });
    },
  });

  const jobs = results.data ?? [];

  return (
    <div className="p-6">
      <div className="mb-1 flex items-center gap-2">
        <Star size={18} className="text-amber-500" />
        <h2 className="text-base font-semibold">
          {results.isLoading ? "Loading…" : `Watchlist · ${jobs.length}`}
        </h2>
      </div>
      <p className="mb-4 text-sm text-slate-500">
        Jobs you've starred to revisit later — e.g. once you line up a referral.
        They stay on your board too; open one to add notes on what it's waiting on.
      </p>

      {!results.isLoading && jobs.length === 0 ? (
        <div className="grid h-48 place-items-center text-center text-sm text-slate-400">
          <div>
            Nothing on your watchlist yet.
            <div className="mt-1 text-xs">
              Tap the <Star size={12} className="mx-0.5 inline -translate-y-px" /> on any
              job to save it here for later.
            </div>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {jobs.map((job) => {
            const style = STATUS_STYLES[job.status as PipelineStatus];
            return (
              <div
                key={job.job_key}
                onClick={() => onOpen(job)}
                className="group flex cursor-pointer select-none flex-col rounded-lg border border-slate-200 bg-white p-3 text-left shadow-sm transition hover:shadow-md"
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
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      unstar.mutate(job.job_key);
                    }}
                    title="Remove from watchlist"
                    className="shrink-0"
                  >
                    <Star size={16} className="fill-amber-400 text-amber-500 hover:text-amber-600" />
                  </button>
                  <span
                    className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${
                      style?.chip ?? "bg-slate-100 text-slate-600"
                    }`}
                  >
                    {job.status}
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
      )}
    </div>
  );
}
