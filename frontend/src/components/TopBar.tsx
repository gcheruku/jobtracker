import { Menu, Search, SlidersHorizontal, X } from "lucide-react";
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
  onMenu,
}: {
  title: string;
  filters: JobFilters;
  setFilters: (f: JobFilters) => void;
  onMenu?: () => void;
}) {
  return (
    <div className="sticky top-0 z-10 border-b border-slate-200 bg-white/80 px-4 py-3 backdrop-blur sm:px-6">
      <div className="flex flex-wrap items-center gap-3">
        <button
          onClick={onMenu}
          className="-ml-1 grid h-9 w-9 shrink-0 place-items-center rounded-lg text-slate-500 hover:bg-slate-100 md:hidden"
          title="Menu"
        >
          <Menu size={20} />
        </button>

        <h1 className="mr-2 text-xl font-semibold tracking-tight">{title}</h1>

        <div className="relative min-w-[160px] flex-1 sm:min-w-[220px]">
          <Search
            size={16}
            className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
          />
          <input
            value={filters.q ?? ""}
            onChange={(e) => setFilters({ ...filters, q: e.target.value })}
            placeholder="Search roles, companies, locations…"
            className="w-full rounded-lg border border-slate-200 bg-slate-50 py-2 pl-9 pr-8 text-sm outline-none focus:border-indigo-400 focus:bg-white"
          />
          {filters.q && (
            <button
              onClick={() => setFilters({ ...filters, q: "" })}
              title="Clear search"
              className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-0.5 text-slate-400 hover:bg-slate-200 hover:text-slate-700"
            >
              <X size={15} />
            </button>
          )}
        </div>

        {/* Filters + primary action stay together so the Fetch button never
            ends up stranded alone on its own row. */}
        <div className="ml-auto flex flex-wrap items-center gap-2 sm:gap-3">
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
            className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-600"
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

          <FetchAlertsButton />
        </div>
      </div>
    </div>
  );
}
