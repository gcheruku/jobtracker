import { Menu, Search, X } from "lucide-react";
import type { BoardFilters, JobFilters } from "../lib/types";
import { FetchAlertsButton } from "./FetchAlertsButton";
import { SortMenu } from "./SortMenu";
import { BoardFilterMenu, BoardFilterChips } from "./BoardFilterMenu";

// Board controls (sort + filters) are dashboard-only; other views have their
// own filtering.
export interface BoardControls {
  filters: BoardFilters;
  setFilters: (f: BoardFilters) => void;
  sort: string;
  setSort: (s: string) => void;
}

export function TopBar({
  title,
  filters,
  setFilters,
  onMenu,
  board,
}: {
  title: string;
  filters: JobFilters;
  setFilters: (f: JobFilters) => void;
  onMenu?: () => void;
  board?: BoardControls;
}) {
  return (
    <div className="sticky top-0 z-10 border-b border-slate-200 bg-white/80 px-4 py-3 backdrop-blur sm:px-6">
      {/* Row 1: menu + title + primary action */}
      <div className="flex items-center gap-3">
        <button
          onClick={onMenu}
          className="-ml-1 grid h-9 w-9 shrink-0 place-items-center rounded-lg text-slate-500 hover:bg-slate-100 md:hidden"
          title="Menu"
        >
          <Menu size={20} />
        </button>

        <h1 className="text-xl font-semibold tracking-tight">{title}</h1>

        <div className="ml-auto">
          <FetchAlertsButton />
        </div>
      </div>

      {/* Row 2: search + (dashboard only) sort and filters */}
      <div className="mt-3 flex items-center gap-2 sm:gap-3">
        <div className="relative flex-1">
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

        {board && (
          <>
            <SortMenu value={board.sort} onChange={board.setSort} />
            <BoardFilterMenu value={board.filters} onChange={board.setFilters} />
          </>
        )}
      </div>

      {/* Row 3: active filter chips (dashboard only) */}
      {board && (
        <div className="mt-2 empty:mt-0">
          <BoardFilterChips value={board.filters} onChange={board.setFilters} />
        </div>
      )}
    </div>
  );
}
