import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RotateCcw, Trash2, Archive, ChevronDown } from "lucide-react";
import { api } from "../lib/api";
import { STATUS_STYLES, initials } from "../lib/ui";
import { SourceTag } from "./SourceTag";
import type { Job, JobFilters, PipelineStatus } from "../lib/types";

// The status shown for an inactive job: skipped jobs read as "Skipped", else
// their own status. (Preference mismatches have their own dedicated view.)
function label(job: Job): string {
  if (job.ignored) return "Skipped";
  return job.status;
}

const STATUS_OPTIONS = ["All", "Skipped", "Rejected", "Expired"];

export function InactiveView({ filters }: { filters: JobFilters }) {
  const qc = useQueryClient();
  const [statusFilter, setStatusFilter] = useState("All");
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const jobs = useQuery({
    queryKey: ["jobs", "inactive", filters],
    queryFn: () => api.listJobs({ ...filters, off_board: true }),
  });

  const rows = useMemo(() => {
    const all = jobs.data ?? [];
    return statusFilter === "All"
      ? all
      : all.filter((j) => label(j) === statusFilter);
  }, [jobs.data, statusFilter]);

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["jobs"] });
    qc.invalidateQueries({ queryKey: ["stats"] });
    qc.invalidateQueries({ queryKey: ["activity"] });
    setSelected(new Set());
  };

  // Single-row restore: clear skipped/mismatched flags; move off-board
  // (Rejected/Expired) ones to Saved.
  const restoreOne = useMutation({
    mutationFn: (job: Job) =>
      job.ignored || job.mismatched
        ? api.restoreJob(job.job_key)
        : api.moveStatus(job.job_key, "Saved"),
    onSuccess: refresh,
  });
  const removeOne = useMutation({
    mutationFn: (k: string) => api.deleteJob(k),
    onSuccess: refresh,
  });
  const bulkRestore = useMutation({
    mutationFn: (keys: string[]) => api.bulkRestore(keys),
    onSuccess: refresh,
  });
  const bulkDelete = useMutation({
    mutationFn: (keys: string[]) => api.bulkDelete(keys),
    onSuccess: refresh,
  });

  const allSelected = rows.length > 0 && rows.every((j) => selected.has(j.job_key));
  const someSelected = selected.size > 0;

  const toggle = (key: string) =>
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });
  const toggleAll = () =>
    setSelected(allSelected ? new Set() : new Set(rows.map((j) => j.job_key)));

  const selectedKeys = () => rows.filter((j) => selected.has(j.job_key)).map((j) => j.job_key);
  const busy = bulkRestore.isPending || bulkDelete.isPending;

  return (
    <div className="px-4 pb-4 sm:px-6 sm:pb-6">
      {/* Description scrolls away with the list. */}
      <div className="flex items-center gap-2 pb-3 pt-4 text-slate-500 sm:pt-6">
        <Archive size={18} />
        <p className="text-sm">
          Jobs not on the active board — skipped, rejected, or expired.
        </p>
      </div>

      {/* Only the dropdown pins flush to the top while the list scrolls. */}
      <div className="sticky top-0 z-10 -mx-4 mb-4 flex bg-slate-100 px-4 pb-3 pt-1 sm:-mx-6 sm:px-6">
        <div className="relative w-full sm:ml-auto sm:w-auto">
          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setSelected(new Set());
            }}
            className="w-full cursor-pointer appearance-none rounded-lg border border-slate-200 bg-white px-3 py-2.5 pr-8 text-sm font-medium text-slate-600 outline-none focus:border-indigo-400 sm:py-2"
          >
            {STATUS_OPTIONS.map((s) => (
              <option key={s} value={s}>
                {s === "All" ? "All statuses" : s}
              </option>
            ))}
          </select>
          <ChevronDown
            size={16}
            className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400"
          />
        </div>
      </div>

      {/* Bulk action bar */}
      {someSelected && (
        <div className="mb-3 flex flex-wrap items-center gap-2 rounded-lg border border-indigo-200 bg-indigo-50 px-3 py-2 text-sm sm:gap-3 sm:px-4">
          <span className="font-medium text-indigo-700">{selected.size} selected</span>
          <button
            disabled={busy}
            onClick={() => bulkRestore.mutate(selectedKeys())}
            className="inline-flex items-center gap-1 rounded-md border border-slate-300 bg-white px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-100 disabled:opacity-50"
          >
            <RotateCcw size={13} /> Restore selected
          </button>
          <button
            disabled={busy}
            onClick={() => {
              if (confirm(`Permanently delete ${selected.size} job(s)?`))
                bulkDelete.mutate(selectedKeys());
            }}
            className="inline-flex items-center gap-1 rounded-md border border-rose-300 bg-white px-2.5 py-1 text-xs font-medium text-rose-600 hover:bg-rose-50 disabled:opacity-50"
          >
            <Trash2 size={13} /> Delete selected
          </button>
          <button
            onClick={() => setSelected(new Set())}
            className="ml-auto text-xs text-slate-500 hover:text-slate-800"
          >
            Clear
          </button>
        </div>
      )}

      {/* Mobile: card list */}
      <div className="md:hidden">
        {rows.length > 0 && (
          <label className="mb-2 flex items-center gap-2 px-1 text-xs font-medium text-slate-500">
            <input
              type="checkbox"
              checked={allSelected}
              onChange={toggleAll}
              className="h-4 w-4 rounded border-slate-300 text-indigo-600"
            />
            Select all ({rows.length})
          </label>
        )}
        <div className="space-y-2">
          {rows.map((j) => {
            const lbl = label(j);
            const style = STATUS_STYLES[lbl as PipelineStatus];
            const isSel = selected.has(j.job_key);
            return (
              <div
                key={j.job_key}
                onClick={() => toggle(j.job_key)}
                className={`cursor-pointer rounded-xl border bg-white p-3 shadow-sm transition ${
                  isSel
                    ? "border-indigo-400 bg-indigo-50/50 ring-1 ring-indigo-300"
                    : "border-slate-200 hover:border-slate-300"
                }`}
              >
                <div className="flex items-start gap-3">
                  <div className="grid h-8 w-8 shrink-0 place-items-center rounded-md bg-slate-100 text-xs font-bold text-slate-500">
                    {initials(j.company)}
                  </div>
                  <div className="min-w-0 flex-1">
                    {j.url ? (
                      <a
                        href={j.url}
                        target="_blank"
                        rel="noreferrer"
                        onClick={(e) => e.stopPropagation()}
                        className="block truncate text-sm font-semibold text-indigo-700 hover:underline"
                      >
                        {j.title}
                      </a>
                    ) : (
                      <span className="block truncate text-sm font-semibold">{j.title}</span>
                    )}
                    <div className="truncate text-xs text-slate-500">{j.company}</div>
                    <div className="mt-1.5 flex items-center gap-1.5">
                      <SourceTag source={j.source} />
                      <span
                        className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${
                          style?.chip ?? "bg-slate-100 text-slate-600"
                        }`}
                      >
                        {lbl}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
          {rows.length === 0 && (
            <div className="rounded-xl border border-slate-200 bg-white px-4 py-10 text-center text-sm text-slate-400">
              No {statusFilter === "All" ? "inactive" : statusFilter.toLowerCase()} jobs.
            </div>
          )}
        </div>
      </div>

      {/* Desktop: table */}
      <div className="hidden overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm md:block">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-400">
            <tr>
              <th className="w-10 px-4 py-3">
                <input
                  type="checkbox"
                  checked={allSelected}
                  onChange={toggleAll}
                  className="h-4 w-4 rounded border-slate-300 text-indigo-600"
                />
              </th>
              <th className="px-4 py-3">Role</th>
              <th className="px-4 py-3">Company</th>
              <th className="px-4 py-3">Source</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {rows.map((j) => {
              const lbl = label(j);
              const style = STATUS_STYLES[lbl as PipelineStatus];
              return (
                <tr
                  key={j.job_key}
                  className={selected.has(j.job_key) ? "bg-indigo-50/40" : "hover:bg-slate-50"}
                >
                  <td className="px-4 py-3">
                    <input
                      type="checkbox"
                      checked={selected.has(j.job_key)}
                      onChange={() => toggle(j.job_key)}
                      className="h-4 w-4 rounded border-slate-300 text-indigo-600"
                    />
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <div className="grid h-7 w-7 place-items-center rounded bg-slate-100 text-[10px] font-bold text-slate-500">
                        {initials(j.company)}
                      </div>
                      {j.url ? (
                      <a
                        href={j.url}
                        target="_blank"
                        rel="noreferrer"
                        className="font-medium text-indigo-700 hover:underline"
                      >
                        {j.title}
                      </a>
                    ) : (
                      <span className="font-medium">{j.title}</span>
                    )}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-slate-500">{j.company}</td>
                  <td className="px-4 py-3"><SourceTag source={j.source} /></td>
                  <td className="px-4 py-3">
                    <span
                      className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${
                        style?.chip ?? "bg-slate-100 text-slate-600"
                      }`}
                    >
                      {lbl}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex justify-end gap-2">
                      <button
                        onClick={() => restoreOne.mutate(j)}
                        title="Move back to the board (Saved)"
                        className="inline-flex items-center gap-1 rounded-md border border-slate-200 px-2.5 py-1 text-xs font-medium text-slate-600 hover:bg-slate-100"
                      >
                        <RotateCcw size={13} /> Restore
                      </button>
                      <button
                        onClick={() => {
                          if (confirm(`Permanently delete "${j.title}"?`))
                            removeOne.mutate(j.job_key);
                        }}
                        className="inline-flex items-center gap-1 rounded-md border border-rose-200 px-2.5 py-1 text-xs font-medium text-rose-600 hover:bg-rose-50"
                      >
                        <Trash2 size={13} /> Delete
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
            {rows.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-10 text-center text-slate-400">
                  No {statusFilter === "All" ? "inactive" : statusFilter.toLowerCase()} jobs.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
