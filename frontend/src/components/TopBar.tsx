import { EyeOff, Menu, Search, X } from "lucide-react";
import type { BoardFilters, Job, JobFilters } from "../lib/types";
import { AddJobButton } from "./AddJobButton";
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
  onJobAdded,
}: {
  title: string;
  filters: JobFilters;
  setFilters: (f: JobFilters) => void;
  onMenu?: () => void;
  board?: BoardControls;
  // When provided (dashboard), shows the "Add job" button; called with the
  // newly-created job so the parent can open it.
  onJobAdded?: (job: Job) => void;
}) {
  const searching = (filters.q ?? "").trim() !== "";
  // The single "hide handled" toggle drives both flags in lockstep.
  const hideHandled = !!filters.hide_watchlist && !!filters.hide_pipeline;
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

        <div className="ml-auto flex items-center gap-2">
          {onJobAdded && <AddJobButton onAdded={onJobAdded} />}
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
            onChange={(e) => {
              const q = e.target.value;
              // Search-scoped toggles only make sense with an active query;
              // drop them once the box empties so they don't leak into the board.
              setFilters(
                q.trim() === ""
                  ? { ...filters, q, hide_watchlist: false, hide_pipeline: false }
                  : { ...filters, q }
              );
            }}
            placeholder="Search roles, companies, locations…"
            className="w-full rounded-lg border border-slate-200 bg-slate-50 py-2 pl-9 pr-8 text-sm outline-none focus:border-indigo-400 focus:bg-white"
          />
          {filters.q && (
            <button
              onClick={() =>
                setFilters({ ...filters, q: "", hide_watchlist: false, hide_pipeline: false })
              }
              title="Clear search"
              className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-0.5 text-slate-400 hover:bg-slate-200 hover:text-slate-700"
            >
              <X size={15} />
            </button>
          )}
        </div>

        {/* How the search query is matched. "Exact phrase" matches whole words
            contiguously, so "software engineer" excludes "...Engineering Manager". */}
        <select
          value={filters.match ?? "all"}
          onChange={(e) =>
            setFilters({ ...filters, match: e.target.value as JobFilters["match"] })
          }
          title="How search matches your query"
          className="shrink-0 cursor-pointer rounded-lg border border-slate-200 bg-white px-2.5 py-2 text-sm text-slate-600 outline-none focus:border-indigo-400"
        >
          <option value="all">All words</option>
          <option value="any">Any word</option>
          <option value="phrase">Exact phrase</option>
        </select>

        {board && (
          <>
            <SortMenu value={board.sort} onChange={board.setSort} />
            <BoardFilterMenu value={board.filters} onChange={board.setFilters} />
          </>
        )}
      </div>

      {/* Row 2b: search-scope toggle — only while a query is active. One control
          hides jobs you've already handled (starred + in-pipeline), leaving the
          untouched Saved pool. Both flags move together. */}
      {searching && (
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <button
            onClick={() => {
              const on = !hideHandled;
              setFilters({ ...filters, hide_watchlist: on, hide_pipeline: on });
            }}
            title="Hide jobs you've already handled: watchlisted (starred) and in-pipeline (Applied / Interviewing / Offer)"
            aria-pressed={hideHandled}
            className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium transition ${
              hideHandled
                ? "border-indigo-300 bg-indigo-50 text-indigo-700"
                : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
            }`}
          >
            <EyeOff
              size={13}
              className={hideHandled ? "text-indigo-500" : "text-slate-400"}
            />
            Hide starred &amp; in-pipeline
          </button>
        </div>
      )}

      {/* Row 3: active filter chips (dashboard only) */}
      {board && (
        <div className="mt-2 empty:mt-0">
          <BoardFilterChips value={board.filters} onChange={board.setFilters} />
        </div>
      )}
    </div>
  );
}
