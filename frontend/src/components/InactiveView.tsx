import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RotateCcw, Trash2, Archive } from "lucide-react";
import { api } from "../lib/api";
import { STATUS_STYLES, initials } from "../lib/ui";
import type { Job, JobFilters, PipelineStatus } from "../lib/types";

export function InactiveView({ filters }: { filters: JobFilters }) {
  const qc = useQueryClient();
  const jobs = useQuery({
    queryKey: ["jobs", "inactive", filters],
    queryFn: () => api.listJobs({ ...filters, off_board: true }),
  });

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["jobs"] });
    qc.invalidateQueries({ queryKey: ["stats"] });
    qc.invalidateQueries({ queryKey: ["activity"] });
  };

  // Bring a job back onto the active board:
  // - skipped jobs are un-ignored (their status maps back to Saved)
  // - Rejected/Expired jobs are moved to the Saved column
  const restore = useMutation({
    mutationFn: (job: Job) =>
      job.ignored ? api.restoreJob(job.job_key) : api.moveStatus(job.job_key, "Saved"),
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
          Jobs that aren't on the active board — skipped, rejected, or expired.
          They stay in your database; restore one to send it back to the board
          (Saved), or delete it permanently.
        </p>
      </div>

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-400">
            <tr>
              <th className="px-4 py-3">Role</th>
              <th className="px-4 py-3">Company</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {jobs.data?.map((j) => {
              // Skipped jobs surface a "Skipped" status; others show their own.
              const label = j.ignored ? "Skipped" : (j.status as PipelineStatus);
              const style = STATUS_STYLES[label as PipelineStatus];
              return (
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
                  <td className="px-4 py-3">
                    <span
                      className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${
                        style?.chip ?? "bg-slate-100 text-slate-600"
                      }`}
                    >
                      {label}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex justify-end gap-2">
                      <button
                        onClick={() => restore.mutate(j)}
                        title="Move back to the board (Saved)"
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
              );
            })}
            {jobs.data?.length === 0 && (
              <tr>
                <td colSpan={4} className="px-4 py-10 text-center text-slate-400">
                  No inactive jobs.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
