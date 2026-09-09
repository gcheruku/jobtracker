import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  RotateCcw,
  Trash2,
  Archive,
  ChevronDown,
  ChevronUp,
  ChevronsUpDown,
} from "lucide-react";
import { api } from "../lib/api";
import { STATUS_STYLES, initials, shortDate } from "../lib/ui";
import { SourceTag } from "./SourceTag";
import type { Job, JobFilters, PipelineStatus } from "../lib/types";

// The status shown for an inactive job: skipped jobs read as "Skipped", else
// their own status. (Preference mismatches have their own dedicated view.)
function label(job: Job): string {
  if (job.ignored) return "Skipped";
  return job.status;
}

const STATUS_OPTIONS = ["All", "Skipped", "Rejected", "Expired"];

type SortKey = "title" | "company" | "source" | "status" | "saved";
type SortDir = "asc" | "desc";
type Sort = { key: SortKey; dir: SortDir };

// Columns whose natural first click is newest/highest first.
const DESC_FIRST: SortKey[] = ["saved"];

function compare(a: Job, b: Job, key: SortKey): number {
  if (key === "saved") {
    // Missing timestamps read as the epoch, so they group at the oldest end
    // instead of scattering through the list.
    const av = a.inserted_at ? Date.parse(a.inserted_at) : 0;
    const bv = b.inserted_at ? Date.parse(b.inserted_at) : 0;
    return (Number.isNaN(av) ? 0 : av) - (Number.isNaN(bv) ? 0 : bv);
  }
  const text = (j: Job) =>
    key === "status" ? label(j) : (j[key] ?? "");
  return text(a).localeCompare(text(b), undefined, { sensitivity: "base" });
}

// A column header that sorts on click. The inactive state still shows a
// (dimmed) arrow so it's obvious every column can be sorted.
function SortHeader({
  text,
  sortKey,
  sort,
  onSort,
}: {
  text: string;
  sortKey: SortKey;
  sort: Sort | null;
  onSort: (key: SortKey) => void;
}) {
  const active = sort?.key === sortKey;
  const Icon = !active ? ChevronsUpDown : sort.dir === "asc" ? ChevronUp : ChevronDown;
  return (
    <th
      className="px-4 py-3"
      aria-sort={active ? (sort.dir === "asc" ? "ascending" : "descending") : "none"}
    >
      <button
        type="button"
        onClick={() => onSort(sortKey)}
        className={`inline-flex select-none items-center gap-1 uppercase tracking-wide hover:text-slate-600 ${
          active ? "text-slate-600" : ""
        }`}
      >
        {text}
        <Icon size={13} className={active ? "" : "opacity-40"} />
      </button>
    </th>
  );
}

export function InactiveView({ filters }: { filters: JobFilters }) {
  const qc = useQueryClient();
  const [statusFilter, setStatusFilter] = useState("All");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  // Row index of the last checkbox clicked, used as the far end of a
  // shift-click range. Reset whenever the visible rows change.
  const [anchor, setAnchor] = useState<number | null>(null);
  // null = leave the server's ordering (most recent first) alone.
  const [sort, setSort] = useState<Sort | null>(null);

  const jobs = useQuery({
    queryKey: ["jobs", "inactive", filters],
    queryFn: () => api.listJobs({ ...filters, off_board: true }),
  });

  const rows = useMemo(() => {
    const all = jobs.data ?? [];
    const filtered =
      statusFilter === "All" ? all : all.filter((j) => label(j) === statusFilter);
    if (!sort) return filtered;
    const dir = sort.dir === "asc" ? 1 : -1;
    return [...filtered].sort((a, b) => compare(a, b, sort.key) * dir);
  }, [jobs.data, statusFilter, sort]);

  // Click a column to sort by it, click again to flip. Selections survive
  // (they're keyed by job), but the shift-range anchor is a row index, so it
  // has to go when the order changes.
  const sortBy = (key: SortKey) => {
    setSort((prev) =>
      prev?.key === key
        ? { key, dir: prev.dir === "asc" ? "desc" : "asc" }
        : { key, dir: DESC_FIRST.includes(key) ? "desc" : "asc" },
    );
    setAnchor(null);
  };

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["jobs"] });
    qc.invalidateQueries({ queryKey: ["stats"] });
    qc.invalidateQueries({ queryKey: ["activity"] });
    setSelected(new Set());
    setAnchor(null);
  };

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

  // Toggle one row. With shift held, every row between the previous click and
  // this one takes the state this row is moving to — shift-click an unselected
  // row to select the whole span, a selected one to clear it.
  const toggle = (index: number, shiftKey = false) => {
    const job = rows[index];
    if (!job) return;
    setSelected((prev) => {
      const next = new Set(prev);
      const on = !prev.has(job.job_key);
      const from = shiftKey && anchor !== null ? anchor : index;
      const [lo, hi] = from <= index ? [from, index] : [index, from];
      for (const j of rows.slice(lo, hi + 1)) {
        on ? next.add(j.job_key) : next.delete(j.job_key);
      }
      return next;
    });
    setAnchor(index);
  };
  const toggleAll = () => {
    setSelected(allSelected ? new Set() : new Set(rows.map((j) => j.job_key)));
    setAnchor(null);
  };

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

      {/* Filter + bulk actions pin flush to the top while the list scrolls,
          so the actions stay reachable however far down the list you select. */}
      <div className="sticky top-0 z-10 -mx-4 mb-4 bg-slate-100 px-4 pb-3 pt-1 sm:-mx-6 sm:px-6">
        <div className="flex">
          <div className="relative w-full sm:ml-auto sm:w-auto">
            <select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value);
                setSelected(new Set());
                setAnchor(null);
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

        {/* Bulk action bar — the only place restore/delete live, so acting on a
            single job means selecting its row first. */}
        {someSelected && (
          <div className="mt-3 flex flex-wrap items-center gap-2 rounded-lg border border-indigo-200 bg-indigo-50 px-3 py-2 text-sm sm:gap-3 sm:px-4">
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
              onClick={() => {
                setSelected(new Set());
                setAnchor(null);
              }}
              className="ml-auto text-xs text-slate-500 hover:text-slate-800"
            >
              Clear
            </button>
          </div>
        )}
      </div>

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
          {rows.map((j, i) => {
            const lbl = label(j);
            const style = STATUS_STYLES[lbl as PipelineStatus];
            const isSel = selected.has(j.job_key);
            return (
              <div
                key={j.job_key}
                onClick={(e) => toggle(i, e.shiftKey)}
                className={`cursor-pointer select-none rounded-xl border bg-white p-3 shadow-sm transition ${
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
                        className="block break-words text-sm font-semibold text-indigo-700 hover:underline"
                      >
                        {j.title}
                      </a>
                    ) : (
                      <span className="block break-words text-sm font-semibold">{j.title}</span>
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
                    {(j.inserted_at || (anchor !== null && anchor !== i)) && (
                      <div className="mt-1 flex items-center gap-2 text-[11px] text-slate-400">
                        {j.inserted_at && <span>Saved {shortDate(j.inserted_at)}</span>}
                        {anchor !== null && anchor !== i && (
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              toggle(i, true);
                            }}
                            className="ml-auto rounded border border-slate-200 px-1.5 py-0.5 font-medium text-slate-500"
                          >
                            {isSel ? "Clear to here" : "Select to here"}
                          </button>
                        )}
                      </div>
                    )}
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
              <SortHeader text="Role" sortKey="title" sort={sort} onSort={sortBy} />
              <SortHeader text="Company" sortKey="company" sort={sort} onSort={sortBy} />
              <SortHeader text="Source" sortKey="source" sort={sort} onSort={sortBy} />
              <SortHeader text="Status" sortKey="status" sort={sort} onSort={sortBy} />
              <SortHeader text="Saved" sortKey="saved" sort={sort} onSort={sortBy} />
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {rows.map((j, i) => {
              const lbl = label(j);
              const style = STATUS_STYLES[lbl as PipelineStatus];
              return (
                <tr
                  key={j.job_key}
                  onClick={(e) => toggle(i, e.shiftKey)}
                  className={`cursor-pointer select-none ${
                    selected.has(j.job_key) ? "bg-indigo-50/40" : "hover:bg-slate-50"
                  }`}
                >
                  <td className="px-4 py-3">
                    <input
                      type="checkbox"
                      checked={selected.has(j.job_key)}
                      // onClick (not onChange) so the shift key is visible; the
                      // no-op onChange keeps the input controlled.
                      onChange={() => {}}
                      onClick={(e) => {
                        e.stopPropagation();
                        toggle(i, e.shiftKey);
                      }}
                      title="Shift-click to select a range"
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
                          onClick={(e) => e.stopPropagation()}
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
                  <td
                    className="whitespace-nowrap px-4 py-3 text-slate-500"
                    title={j.inserted_at ?? undefined}
                  >
                    {shortDate(j.inserted_at) || "—"}
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
