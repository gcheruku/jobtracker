import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RotateCcw, Trash2, SlidersHorizontal } from "lucide-react";
import { api } from "../lib/api";
import { initials } from "../lib/ui";
import { MatchBadge } from "./MatchBadge";
import type { JobFilters } from "../lib/types";

function reasonChip(reason: string | null) {
  const r = (reason || "").toLowerCase();
  const cls = r.includes("mi away")
    ? "bg-violet-50 text-violet-700"
    : r.includes("salary")
      ? "bg-emerald-50 text-emerald-700"
      : r.includes("match")
        ? "bg-amber-50 text-amber-700"
        : "bg-slate-100 text-slate-600";
  return (
    <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${cls}`}>
      {reason || "—"}
    </span>
  );
}

export function MismatchedView({ filters }: { filters: JobFilters }) {
  const qc = useQueryClient();
  const jobs = useQuery({
    queryKey: ["jobs", "mismatched", filters],
    queryFn: () => api.listJobs({ ...filters, only_mismatched: true }),
  });

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["jobs"] });
    qc.invalidateQueries({ queryKey: ["stats"] });
  };
  const restore = useMutation({
    mutationFn: (k: string) => api.restoreJob(k),
    onSuccess: refresh,
  });
  const remove = useMutation({
    mutationFn: (k: string) => api.deleteJob(k),
    onSuccess: refresh,
  });

  const rows = jobs.data ?? [];

  return (
    <div className="p-6">
      <div className="mb-4 flex items-center gap-2 text-slate-500">
        <SlidersHorizontal size={18} />
        <p className="text-sm">
          Jobs moved off the board because they don't match your preferences.
          Restore one to send it back to the board, or delete it.
        </p>
      </div>

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-400">
            <tr>
              <th className="px-4 py-3">Role</th>
              <th className="px-4 py-3">Company</th>
              <th className="px-4 py-3">Location</th>
              <th className="px-4 py-3">Salary</th>
              <th className="px-4 py-3">Match</th>
              <th className="px-4 py-3">Reason</th>
              <th className="px-4 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {rows.map((j) => (
              <tr key={j.job_key} className="hover:bg-slate-50">
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <div className="grid h-7 w-7 shrink-0 place-items-center rounded bg-slate-100 text-[10px] font-bold text-slate-500">
                      {initials(j.company)}
                    </div>
                    <span className="font-medium">{j.title}</span>
                  </div>
                </td>
                <td className="px-4 py-3 text-slate-500">{j.company}</td>
                <td className="px-4 py-3 text-slate-500">{j.location || "—"}</td>
                <td className="px-4 py-3 text-emerald-600">{j.salary || "—"}</td>
                <td className="px-4 py-3"><MatchBadge job={j} /></td>
                <td className="px-4 py-3">{reasonChip(j.mismatch_reason)}</td>
                <td className="px-4 py-3">
                  <div className="flex justify-end gap-2">
                    <button
                      onClick={() => restore.mutate(j.job_key)}
                      title="Move back to the board"
                      className="inline-flex items-center gap-1 rounded-md border border-slate-200 px-2.5 py-1 text-xs font-medium text-slate-600 hover:bg-slate-100"
                    >
                      <RotateCcw size={13} /> Restore
                    </button>
                    <button
                      onClick={() => {
                        if (confirm(`Permanently delete "${j.title}"?`))
                          remove.mutate(j.job_key);
                      }}
                      className="inline-flex items-center gap-1 rounded-md border border-rose-200 px-2.5 py-1 text-xs font-medium text-rose-600 hover:bg-rose-50"
                    >
                      <Trash2 size={13} /> Delete
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-10 text-center text-slate-400">
                  No mismatched jobs. Set preferences in Settings to filter the board.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
