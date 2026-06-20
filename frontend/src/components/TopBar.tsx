import { Search, SlidersHorizontal } from "lucide-react";
import type { JobFilters } from "../lib/types";
import { FetchAlertsButton } from "./FetchAlertsButton";

const WORK_MODES = ["", "Remote", "Hybrid", "On-site"];
const SORTS = [
  { v: "recent", label: "Most recent" },
  { v: "match", label: "Best match" },
  { v: "company", label: "Company A-Z" },
  { v: "title", label: "Title A-Z" },
];

export function TopBar({
  title,
  filters,
  setFilters,
}: {
  title: string;
  filters: JobFilters;
  setFilters: (f: JobFilters) => void;
}) {
  return (
    <div className="sticky top-0 z-10 border-b border-slate-200 bg-white/80 px-6 py-3 backdrop-blur">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="mr-2 text-xl font-semibold tracking-tight">{title}</h1>

        <div className="relative flex-1 min-w-[220px]">
          <Search
            size={16}
            className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
          />
          <input
            value={filters.q ?? ""}
            onChange={(e) => setFilters({ ...filters, q: e.target.value })}
            placeholder="Search roles, companies, locations…"
            className="w-full rounded-lg border border-slate-200 bg-slate-50 py-2 pl-9 pr-3 text-sm outline-none focus:border-indigo-400 focus:bg-white"
          />
        </div>

        <select
          value={filters.work_mode ?? ""}
          onChange={(e) =>
            setFilters({ ...filters, work_mode: e.target.value || undefined })
          }
          className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-600"
        >
          {WORK_MODES.map((m) => (
            <option key={m} value={m}>
              {m || "Any work mode"}
            </option>
          ))}
        </select>

        <select
          value={filters.sort ?? "recent"}
          onChange={(e) => setFilters({ ...filters, sort: e.target.value })}
          className="flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-600"
        >
          {SORTS.map((s) => (
            <option key={s.v} value={s.v}>
              {s.label}
            </option>
          ))}
        </select>

        <div className="hidden items-center gap-1 rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-400 sm:flex">
          <SlidersHorizontal size={15} />
          Salary
          <input
            type="number"
            placeholder="min"
            className="w-16 bg-transparent text-slate-700 outline-none"
            onChange={(e) =>
              setFilters({
                ...filters,
                min_salary: e.target.value ? Number(e.target.value) : undefined,
              })
            }
          />
        </div>

        <div className="ml-auto">
          <FetchAlertsButton />
        </div>
      </div>
    </div>
  );
}
