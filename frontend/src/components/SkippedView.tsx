import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RotateCcw, Trash2, Archive } from "lucide-react";
import { api } from "../lib/api";
import { initials } from "../lib/ui";
import type { JobFilters } from "../lib/types";

export function SkippedView({ filters }: { filters: JobFilters }) {
  const qc = useQueryClient();
  const jobs = useQuery({
    queryKey: ["jobs", "skipped", filters],
    queryFn: () => api.listJobs({ ...filters, only_ignored: true }),
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

  return (
    <div className="p-6">
      <div className="mb-4 flex items-center gap-2 text-slate-500">
        <Archive size={18} />
        <p className="text-sm">
          Skipped jobs are hidden from the board but still in your database.
          Restore them to the pipeline (they return to Saved) or delete permanently.
        </p>
      </div>

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-400">
            <tr>
              <th className="px-4 py-3">Role</th>
              <th className="px-4 py-3">Company</th>
              <th className="px-4 py-3">Prior status</th>
              <th className="px-4 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {jobs.data?.map((j) => (
              <tr key={j.job_key} className="hover:bg-slate-50">
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <div className="grid h-7 w-7 place-items-center rounded bg-slate-100 text-[10px] font-bold text-slate-500">
                      {initials(j.company)}
                    </div>
                    <span className="font-medium">{j.title}</span>
                  </div>
                </td>
                <td className="px-4 py-3 text-slate-500">{j.company}</td>
                <td className="px-4 py-3 text-slate-500">
                  {j.raw_status || j.status}
                </td>
                <td className="px-4 py-3">
                  <div className="flex justify-end gap-2">
                    <button
                      onClick={() => restore.mutate(j.job_key)}
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
            {jobs.data?.length === 0 && (
              <tr>
                <td colSpan={4} className="px-4 py-10 text-center text-slate-400">
                  No skipped jobs.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
