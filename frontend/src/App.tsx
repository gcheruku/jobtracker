import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useLocation, useNavigate } from "react-router-dom";
import { Activity, ChevronDown, EyeOff, X } from "lucide-react";
import { Sidebar, type View } from "./components/Sidebar";
import { TopBar } from "./components/TopBar";
import { MetricCards } from "./components/MetricCards";
import { KanbanBoard } from "./components/KanbanBoard";
// FocusView and the drawer host pull in JobDetail/ComparePanel/framer-motion,
// none of which are needed for first paint — load them on demand so the
// animation library stays off the critical path.
const FocusView = lazy(() =>
  import("./components/FocusView").then((m) => ({ default: m.FocusView }))
);
const DrawerHost = lazy(() => import("./components/DrawerHost"));
import { ActivityLog } from "./components/ActivityLog";
import { AgentChat } from "./components/AgentChat";
import { InactiveView } from "./components/InactiveView";
import { MismatchedView } from "./components/MismatchedView";
import { WatchlistView } from "./components/WatchlistView";
import { SearchResults } from "./components/SearchResults";
import { SettingsView } from "./components/SettingsView";
import { api } from "./lib/api";
import { BOARD_STATUSES, OFF_BOARD_STATUSES, PIPELINE } from "./lib/types";
import { applyBoardFilters } from "./lib/filters";
import type { BoardFilters, Job, JobFilters, PipelineStatus } from "./lib/types";

// Each screen has a URL so browser back / iOS edge-swipe / refresh / bookmarking
// all work. A job opens as `?job=<key>` on top of the current screen, so the
// list underneath stays mounted (its scroll is preserved) and back closes it.
const VIEW_PATH: Record<View, string> = {
  dashboard: "/",
  watchlist: "/watchlist",
  mismatched: "/mismatched",
  inactive: "/inactive",
  settings: "/settings",
};

function viewForPath(pathname: string): View {
  for (const [v, p] of Object.entries(VIEW_PATH) as [View, string][]) {
    if (p === pathname) return v;
  }
  return "dashboard";
}

export default function App() {
  const qc = useQueryClient();
  const location = useLocation();
  const navigate = useNavigate();
  // Screen + open job are derived from the URL (see VIEW_PATH above).
  const view = viewForPath(location.pathname);
  const openJobKey = new URLSearchParams(location.search).get("job");

  const [filters, setFilters] = useState<JobFilters>({ sort: "recent" });
  // Dashboard-only client-side filters (Filters popup).
  const [boardFilters, setBoardFilters] = useState<BoardFilters>({});
  // Multi-select on the board (Gmail-style avatar checkboxes). anchorKey is the
  // last single-selected card, used as the start of a Shift+click range.
  const [selectedKeys, setSelectedKeys] = useState<Set<string>>(new Set());
  const [anchorKey, setAnchorKey] = useState<string | null>(null);
  // The drawer lives behind a lazy boundary; mount it on the first open and
  // keep it mounted so its slide-out (exit) animation still plays on close.
  const [drawerMounted, setDrawerMounted] = useState(false);
  const [activityOpen, setActivityOpen] = useState(false);
  // Off-canvas sidebar on mobile.
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Changing screen (path) clears multi-select and closes the mobile nav. Note
  // opening a job only changes the query string, so it doesn't trigger this.
  useEffect(() => {
    setSelectedKeys(new Set());
    setAnchorKey(null);
    setSidebarOpen(false);
  }, [location.pathname]);

  const setView = (v: View) => navigate(VIEW_PATH[v]);

  // Open a job as `?job=<key>` on the current screen. Switching jobs (list click
  // / swipe) replaces history so Back returns to the list, not the prior job.
  const goToJob = (j: Job, opts?: { replace?: boolean }) =>
    navigate(
      { pathname: location.pathname, search: `?job=${encodeURIComponent(j.job_key)}` },
      { replace: opts?.replace }
    );
  // Close the detail: pop history when we pushed it in-app (so it feels like a
  // real back), else (deep link / refresh) just strip the ?job= param.
  const closeJob = () =>
    location.key !== "default"
      ? navigate(-1)
      : navigate({ pathname: location.pathname }, { replace: true });

  const toggleSelect = (j: Job) => {
    setAnchorKey(j.job_key);
    setSelectedKeys((prev) => {
      const next = new Set(prev);
      next.has(j.job_key) ? next.delete(j.job_key) : next.add(j.job_key);
      return next;
    });
  };
  // Shift+click: add a contiguous range of cards (within a column) to selection.
  const selectRange = (keys: string[]) =>
    setSelectedKeys((prev) => {
      const next = new Set(prev);
      keys.forEach((k) => next.add(k));
      return next;
    });
  const clearSelection = () => {
    setSelectedKeys(new Set());
    setAnchorKey(null);
  };

  const jobs = useQuery({
    queryKey: ["jobs", "board", filters],
    queryFn: () => api.listJobs({ ...filters, board_only: true }),
  });
  const stats = useQuery({ queryKey: ["stats"], queryFn: api.stats });

  const searching = (filters.q ?? "").trim() !== "";
  // Board jobs after applying the dashboard Filters popup.
  const visibleJobs = useMemo(
    () => applyBoardFilters(jobs.data ?? [], boardFilters),
    [jobs.data, boardFilters]
  );
  const byStatus = stats.data?.by_status ?? {};
  const boardTotal = BOARD_STATUSES.reduce((n, s) => n + (byStatus[s] ?? 0), 0);
  const mismatchedCount = stats.data?.mismatched ?? 0;
  const inactiveCount =
    (stats.data?.ignored ?? 0) +
    OFF_BOARD_STATUSES.reduce((n, s) => n + (byStatus[s] ?? 0), 0);

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["jobs"] });
    qc.invalidateQueries({ queryKey: ["stats"] });
    qc.invalidateQueries({ queryKey: ["activity"] });
  };

  // The job open in the detail overlay (from ?job=). Prefer the cached board
  // copy (carries optimistic updates); fall back to fetching it directly so a
  // deep link / refresh to /?job=KEY still resolves the job.
  const jobQuery = useQuery({
    queryKey: ["job", openJobKey],
    queryFn: () => api.getJob(openJobKey!),
    enabled: !!openJobKey,
  });
  const activeJob = useMemo(
    () =>
      openJobKey
        ? visibleJobs.find((j) => j.job_key === openJobKey) ?? jobQuery.data ?? null
        : null,
    [openJobKey, visibleJobs, jobQuery.data]
  );
  // Board detail is the full-screen focus overlay; watchlist/search use the drawer.
  const boardFocus = view === "dashboard" && !searching ? activeJob : null;
  const drawerJob =
    view === "watchlist" || (view === "dashboard" && searching) ? activeJob : null;
  useEffect(() => {
    if (drawerJob) setDrawerMounted(true);
  }, [drawerJob]);

  // Keep the open job in sync after a change (status move, JD paste, skip, …).
  const onDetailChanged = () => {
    refresh();
    if (openJobKey) qc.invalidateQueries({ queryKey: ["job", openJobKey] });
  };

  // Optimistic status move so the card jumps columns instantly.
  const move = useMutation({
    mutationFn: (v: { key: string; status: PipelineStatus }) =>
      api.moveStatus(v.key, v.status),
    onMutate: async (v) => {
      await qc.cancelQueries({ queryKey: ["jobs", "board", filters] });
      const prev = qc.getQueryData<Job[]>(["jobs", "board", filters]);
      qc.setQueryData<Job[]>(["jobs", "board", filters], (old) =>
        old?.map((j) => (j.job_key === v.key ? { ...j, status: v.status } : j))
      );
      return { prev };
    },
    onError: (_e, _v, ctx) => {
      if (ctx?.prev) qc.setQueryData(["jobs", "board", filters], ctx.prev);
    },
    onSettled: refresh,
  });

  const ignore = useMutation({
    mutationFn: (key: string) => api.ignoreJob(key),
    onSuccess: refresh,
  });

  // Star/unstar a job for later revisit. Optimistic so the board star flips
  // instantly; the Watchlist view and counts reconcile on settle.
  const watchlist = useMutation({
    mutationFn: (v: { key: string; on: boolean }) => api.setWatchlist(v.key, v.on),
    onMutate: async (v) => {
      await qc.cancelQueries({ queryKey: ["jobs", "board", filters] });
      const prev = qc.getQueryData<Job[]>(["jobs", "board", filters]);
      qc.setQueryData<Job[]>(["jobs", "board", filters], (old) =>
        old?.map((j) => (j.job_key === v.key ? { ...j, watchlist: v.on } : j))
      );
      return { prev };
    },
    onError: (_e, _v, ctx) => {
      if (ctx?.prev) qc.setQueryData(["jobs", "board", filters], ctx.prev);
    },
    onSettled: refresh,
  });

  // Bulk actions over the multi-selected board cards (no delete here — that
  // only applies to already-skipped/mismatched jobs in the Inactive view).
  const bulkMove = useMutation({
    // Single request + one DB transaction — reliable for large selections
    // (firing one request per job caused partial failures at scale).
    mutationFn: (status: PipelineStatus) =>
      api.bulkSetStatus([...selectedKeys], status),
    onSuccess: () => {
      refresh();
      clearSelection();
    },
  });
  const bulkSkip = useMutation({
    mutationFn: () => api.bulkIgnore([...selectedKeys]),
    onSuccess: () => {
      refresh();
      clearSelection();
    },
  });
  const bulkBusy = bulkMove.isPending || bulkSkip.isPending;

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar
        view={view}
        setView={setView}
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        counts={{
          dashboard: boardTotal,
          watchlist: stats.data?.watchlist ?? 0,
          mismatched: mismatchedCount,
          inactive: inactiveCount,
        }}
      />

      <main className="relative flex min-w-0 flex-1 flex-col overflow-hidden">
        {/* On mobile the focus view is purely the job detail, so hide the top
            bar (search, filters, Fetch alerts) there. */}
        <div className={boardFocus ? "hidden md:block" : ""}>
          <TopBar
            onMenu={() => setSidebarOpen(true)}
            title={
              view === "dashboard"
                ? "Dashboard"
                : view === "watchlist"
                  ? "Watchlist"
                  : view === "mismatched"
                    ? "Mismatched jobs"
                    : view === "inactive"
                      ? "Inactive jobs"
                      : "Settings"
            }
            filters={filters}
            setFilters={setFilters}
            onJobAdded={view === "dashboard" ? goToJob : undefined}
            board={
              view === "dashboard" && !searching
                ? {
                    filters: boardFilters,
                    setFilters: setBoardFilters,
                    sort: filters.sort ?? "recent",
                    setSort: (s) => setFilters({ ...filters, sort: s }),
                  }
                : undefined
            }
          />
        </div>

        {view === "settings" ? (
          <div className="flex-1 overflow-y-auto">
            <SettingsView />
          </div>
        ) : view === "watchlist" ? (
          <div className="flex-1 overflow-y-auto">
            <WatchlistView onOpen={goToJob} />
          </div>
        ) : view === "mismatched" ? (
          <div className="flex-1 overflow-y-auto">
            <MismatchedView filters={filters} />
          </div>
        ) : view === "inactive" ? (
          <div className="flex-1 overflow-y-auto">
            <InactiveView filters={filters} />
          </div>
        ) : searching ? (
          <div
            className={`flex-1 overflow-y-auto ${selectedKeys.size > 0 ? "pb-24" : ""}`}
          >
            <SearchResults
              filters={filters}
              onOpen={goToJob}
              onToggleSelect={toggleSelect}
              onRangeSelect={selectRange}
              onClearSelection={clearSelection}
              onToggleWatchlist={(j) =>
                watchlist.mutate({ key: j.job_key, on: !j.watchlist })
              }
              anchorKey={anchorKey}
              selectedKeys={selectedKeys}
            />
          </div>
        ) : (
          // No top padding here: the sticky column dropdown pins flush against
          // the top bar (top padding would leave a strip where cards show
          // through while scrolling). The top gap moves onto MetricCards.
          // Extra bottom padding when the selection bar is shown so it doesn't
          // cover the last cards.
          <div
            className={`flex-1 overflow-y-auto px-4 sm:px-6 ${
              selectedKeys.size > 0 ? "pb-24" : "pb-4 sm:pb-6"
            }`}
          >
            <div className="pt-4 sm:pt-6">
              <MetricCards stats={stats.data} />
            </div>

            <div
              className={`mt-6 grid grid-cols-1 gap-6 ${
                activityOpen ? "xl:grid-cols-[1fr_320px]" : ""
              }`}
            >
              <div className="min-w-0">
                <div className="mb-3 flex items-center justify-between">
                  <h2 className="text-base font-semibold">Application pipeline</h2>
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-slate-400">
                      {visibleJobs.length} shown · {boardTotal} active
                    </span>
                    {!activityOpen && (
                      <button
                        onClick={() => setActivityOpen(true)}
                        className="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-white px-2.5 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50"
                      >
                        <Activity size={13} className="text-indigo-600" />
                        Activity
                      </button>
                    )}
                  </div>
                </div>
                {jobs.isLoading ? (
                  <div className="grid h-64 place-items-center text-slate-400">
                    Loading jobs…
                  </div>
                ) : (
                  <KanbanBoard
                    jobs={visibleJobs}
                    onOpen={goToJob}
                    onIgnore={(j) => ignore.mutate(j.job_key)}
                    onToggleWatchlist={(j) =>
                      watchlist.mutate({ key: j.job_key, on: !j.watchlist })
                    }
                    onMove={(key, status) => move.mutate({ key, status })}
                    onToggleSelect={toggleSelect}
                    onRangeSelect={selectRange}
                    anchorKey={anchorKey}
                    selectedKeys={selectedKeys}
                  />
                )}
              </div>

              {/* Desktop (xl): activity sits in the right column. */}
              {activityOpen && (
                <div className="hidden space-y-6 xl:block">
                  <ActivityLog onCollapse={() => setActivityOpen(false)} />
                </div>
              )}
            </div>

            {/* Below xl: activity opens as a full-screen popup. */}
            {activityOpen && (
              <div className="fixed inset-0 z-40 flex flex-col bg-slate-100 xl:hidden">
                <div className="flex items-center justify-between border-b border-slate-200 bg-white px-4 py-3">
                  <div className="flex items-center gap-2">
                    <Activity size={18} className="text-indigo-600" />
                    <h2 className="text-base font-semibold">Recent activity</h2>
                  </div>
                  <button
                    onClick={() => setActivityOpen(false)}
                    title="Close"
                    className="grid h-9 w-9 place-items-center rounded-lg text-slate-400 hover:bg-slate-100 hover:text-slate-700"
                  >
                    <X size={20} />
                  </button>
                </div>
                <div className="flex-1 overflow-y-auto p-4">
                  <ActivityLog hideHeader />
                </div>
              </div>
            )}
          </div>
        )}

        {/* Board detail as a full-screen overlay INSIDE main: the board list
            stays mounted underneath, so returning (Back / iOS edge-swipe)
            restores the list exactly where it was scrolled. */}
        {boardFocus && (
          <Suspense
            fallback={
              <div className="absolute inset-0 z-30 grid place-items-center bg-white text-slate-400">
                Loading…
              </div>
            }
          >
            <div className="absolute inset-0 z-30 flex flex-col bg-white">
              <FocusView
                jobs={visibleJobs}
                selected={boardFocus}
                onSelect={(j) => goToJob(j, { replace: true })}
                onBack={closeJob}
                onChanged={onDetailChanged}
              />
            </div>
          </Suspense>
        )}

        {/* Multi-select action bar — shared by the board and search results
            (both are the dashboard view). Fixed-positioned, so it overlays
            whichever list is showing. */}
        {view === "dashboard" && !boardFocus && selectedKeys.size > 0 && (
          <div className="fixed inset-x-0 bottom-0 z-40 px-3 pb-3">
            <div className="mx-auto flex max-w-2xl flex-wrap items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2.5 shadow-2xl">
              <span className="text-sm font-semibold text-indigo-700">
                {selectedKeys.size} selected
              </span>
              <div className="relative">
                <select
                  value=""
                  disabled={bulkBusy}
                  onChange={(e) => {
                    if (e.target.value) bulkMove.mutate(e.target.value as PipelineStatus);
                  }}
                  className="cursor-pointer appearance-none rounded-lg border border-slate-200 bg-white py-1.5 pl-3 pr-8 text-sm font-medium text-slate-700 outline-none focus:border-indigo-400 disabled:opacity-50"
                >
                  <option value="" disabled>
                    Set status…
                  </option>
                  {PIPELINE.map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>
                <ChevronDown
                  size={15}
                  className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-slate-400"
                />
              </div>
              <button
                onClick={() => bulkSkip.mutate()}
                disabled={bulkBusy}
                className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-50"
              >
                <EyeOff size={15} /> Skip
              </button>
              <button
                onClick={clearSelection}
                className="ml-auto inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-800"
              >
                <X size={16} /> Clear
              </button>
            </div>
          </div>
        )}
      </main>

      {drawerMounted && (
        <Suspense fallback={null}>
          <DrawerHost job={drawerJob} onClose={closeJob} onChanged={onDetailChanged} />
        </Suspense>
      )}

      <AgentChat />
    </div>
  );
}
