import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RotateCcw, Trash2, SlidersHorizontal } from "lucide-react";
import { api } from "../lib/api";
import { initials } from "../lib/ui";
import { MatchBadge } from "./MatchBadge";
import type { Job, JobFilters } from "../lib/types";

// Map a reason string to a filter category.
function reasonCategory(reason: string | null): string {
  const r = (reason || "").toLowerCase();
  if (r.includes("mi away")) return "Distance";
  if (r.includes("salary")) return "Salary";
  if (r.includes("match")) return "Match score";
  if (r.includes("keyword")) return "Keyword";
  if (r.includes("company")) return "Company";
  return "Other";
}

const REASON_OPTIONS = ["All", "Distance", "Salary", "Match score", "Keyword", "Company"];

function reasonChip(reason: string | null) {
  const cat = reasonCategory(reason);
  const cls =
    cat === "Distance"
      ? "bg-violet-50 text-violet-700"
      : cat === "Salary"
        ? "bg-emerald-50 text-emerald-700"
        : cat === "Match score"
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
  const [reasonFilter, setReasonFilter] = useState("All");
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const jobs = useQuery({
    queryKey: ["jobs", "mismatched", filters],
    queryFn: () => api.listJobs({ ...filters, only_mismatched: true }),
  });

  const rows = useMemo(() => {
    const all = jobs.data ?? [];
    return reasonFilter === "All"
      ? all
      : all.filter((j) => reasonCategory(j.mismatch_reason) === reasonFilter);
  }, [jobs.data, reasonFilter]);

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["jobs"] });
    qc.invalidateQueries({ queryKey: ["stats"] });
    setSelected(new Set());
  };
  const restore = useMutation({ mutationFn: (k: string) => api.restoreJob(k), onSuccess: refresh });
  const remove = useMutation({ mutationFn: (k: string) => api.deleteJob(k), onSuccess: refresh });
  const bulkRestore = useMutation({ mutationFn: (ks: string[]) => api.bulkRestore(ks), onSuccess: refresh });
  const bulkDelete = useMutation({ mutationFn: (ks: string[]) => api.bulkDelete(ks), onSuccess: refresh });

  const allSelected = rows.length > 0 && rows.every((j) => selected.has(j.job_key));
  const toggle = (k: string) =>
    setSelected((p) => {
      const n = new Set(p);
      n.has(k) ? n.delete(k) : n.add(k);
      return n;
    });
  const toggleAll = () =>
    setSelected(allSelected ? new Set() : new Set(rows.map((j) => j.job_key)));
  const selectedKeys = () => rows.filter((j) => selected.has(j.job_key)).map((j) => j.job_key);
  const busy = bulkRestore.isPending || bulkDelete.isPending;

  return (
    <div className="p-6">
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2 text-slate-500">
          <SlidersHorizontal size={18} />
          <p className="text-sm">Jobs off the board because they don't match your preferences.</p>
        </div>
        <select
          value={reasonFilter}
          onChange={(e) => {
            setReasonFilter(e.target.value);
            setSelected(new Set());
          }}
          className="ml-auto rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-600"
        >
          {REASON_OPTIONS.map((r) => (
            <option key={r} value={r}>{r === "All" ? "All reasons" : r}</option>
          ))}
        </select>
      </div>

      {selected.size > 0 && (
        <div className="mb-3 flex items-center gap-3 rounded-lg border border-indigo-200 bg-indigo-50 px-4 py-2 text-sm">
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
          <button onClick={() => setSelected(new Set())} className="ml-auto text-xs text-slate-500 hover:text-slate-800">
            Clear
          </button>
        </div>
      )}

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-400">
            <tr>
              <th className="w-10 px-4 py-3">
                <input type="checkbox" checked={allSelected} onChange={toggleAll} className="h-4 w-4 rounded border-slate-300 text-indigo-600" />
              </th>
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
            {rows.map((j: Job) => (
              <tr key={j.job_key} className={selected.has(j.job_key) ? "bg-indigo-50/40" : "hover:bg-slate-50"}>
                <td className="px-4 py-3">
                  <input type="checkbox" checked={selected.has(j.job_key)} onChange={() => toggle(j.job_key)} className="h-4 w-4 rounded border-slate-300 text-indigo-600" />
                </td>
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
                    <button onClick={() => restore.mutate(j.job_key)} title="Move back to the board" className="inline-flex items-center gap-1 rounded-md border border-slate-200 px-2.5 py-1 text-xs font-medium text-slate-600 hover:bg-slate-100">
                      <RotateCcw size={13} /> Restore
                    </button>
                    <button onClick={() => { if (confirm(`Permanently delete "${j.title}"?`)) remove.mutate(j.job_key); }} className="inline-flex items-center gap-1 rounded-md border border-rose-200 px-2.5 py-1 text-xs font-medium text-rose-600 hover:bg-rose-50">
                      <Trash2 size={13} /> Delete
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={8} className="px-4 py-10 text-center text-slate-400">
                  No {reasonFilter === "All" ? "mismatched" : reasonFilter.toLowerCase()} jobs.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
