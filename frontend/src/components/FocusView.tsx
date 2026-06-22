import { useMemo, useState } from "react";
import { ArrowLeft, ChevronDown, MapPin } from "lucide-react";
import { BOARD_STATUSES, type Job, type PipelineStatus } from "../lib/types";
import { STATUS_STYLES, initials } from "../lib/ui";
import { MatchBadge } from "./MatchBadge";
import { JobDetail } from "./JobDetail";

function ListItem({
  job,
  active,
  onSelect,
}: {
  job: Job;
  active: boolean;
  onSelect: (j: Job) => void;
}) {
  return (
    <button
      onClick={() => onSelect(job)}
      className={`w-full rounded-lg border p-3 text-left transition ${
        active
          ? "border-indigo-300 bg-indigo-50/70 shadow-sm"
          : "border-slate-200 bg-white hover:border-slate-300 hover:shadow-sm"
      }`}
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
        <MatchBadge job={job} />
      </div>
      {(job.work_mode || job.location) && (
        <div className="mt-2 flex items-center gap-1 truncate text-[11px] text-slate-400">
          <MapPin size={12} />
          {job.work_mode || job.location}
        </div>
      )}
    </button>
  );
}

/**
 * Full-screen detail view: the jobs in the chosen column are listed down the
 * left, the selected job's details fill the right. The status dropdown switches
 * which column is browsed without leaving the view; a back arrow returns to the
 * board. On mobile the list collapses into an off-canvas drawer.
 */
export function FocusView({
  jobs,
  selected,
  onSelect,
  onBack,
  onChanged,
}: {
  jobs: Job[];
  selected: Job;
  onSelect: (j: Job) => void;
  onBack: () => void;
  onChanged: () => void;
}) {
  const [statusFilter, setStatusFilter] = useState<PipelineStatus>(selected.status);
  const style = STATUS_STYLES[statusFilter];

  const counts = useMemo(() => {
    const map = Object.fromEntries(BOARD_STATUSES.map((s) => [s, 0])) as Record<
      PipelineStatus,
      number
    >;
    for (const j of jobs) if (map[j.status] != null) map[j.status]++;
    return map;
  }, [jobs]);

  const columnJobs = useMemo(
    () => jobs.filter((j) => j.status === statusFilter),
    [jobs, statusFilter]
  );

  function changeStatus(s: PipelineStatus) {
    setStatusFilter(s);
    const first = jobs.find((j) => j.status === s);
    if (first) onSelect(first);
  }

  return (
    <div className="relative flex flex-1 overflow-hidden">
      {/* Left: jobs in the chosen column (desktop only; mobile is detail-only) */}
      <aside className="hidden w-80 shrink-0 flex-col border-r border-slate-200 bg-slate-50 md:flex">
        <div className="flex flex-col gap-3 border-b border-slate-200 px-4 py-4">
          <button
            onClick={onBack}
            className="flex w-fit items-center gap-1.5 text-sm font-medium text-slate-500 transition hover:text-slate-800"
          >
            <ArrowLeft size={16} /> Back to board
          </button>
          <div className="relative">
            <span
              className={`pointer-events-none absolute left-3 top-1/2 h-2.5 w-2.5 -translate-y-1/2 rounded-full ${style.dot}`}
            />
            <select
              value={statusFilter}
              onChange={(e) => changeStatus(e.target.value as PipelineStatus)}
              className="w-full cursor-pointer appearance-none rounded-lg border border-slate-200 bg-white py-2 pl-7 pr-8 text-sm font-semibold text-slate-700 outline-none transition hover:border-slate-300 focus:border-indigo-400"
            >
              {BOARD_STATUSES.map((s) => (
                <option key={s} value={s} disabled={(counts[s] ?? 0) === 0}>
                  {s} ({counts[s] ?? 0})
                </option>
              ))}
            </select>
            <ChevronDown
              size={16}
              className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400"
            />
          </div>
        </div>
        <div className="thin-scroll flex-1 space-y-2 overflow-y-auto p-3">
          {columnJobs.map((job) => (
            <ListItem
              key={job.job_key}
              job={job}
              active={job.job_key === selected.job_key}
              onSelect={onSelect}
            />
          ))}
          {columnJobs.length === 0 && (
            <div className="grid h-24 place-items-center text-xs text-slate-400">
              No jobs in this column.
            </div>
          )}
        </div>
      </aside>

      {/* Right: selected job detail */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* Mobile-only bar: back to board (the view is purely the job detail) */}
        <div className="flex items-center border-b border-slate-200 bg-white px-4 py-2.5 md:hidden">
          <button
            onClick={onBack}
            className="flex items-center gap-1.5 text-sm font-medium text-slate-600 transition hover:text-slate-900"
          >
            <ArrowLeft size={18} /> Back
          </button>
        </div>
        <div className="min-h-0 flex-1">
          <JobDetail
            key={selected.job_key}
            job={selected}
            onChanged={onChanged}
            onClose={onBack}
            showClose={false}
          />
        </div>
      </div>
    </div>
  );
}
