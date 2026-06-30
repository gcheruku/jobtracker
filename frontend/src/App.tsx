import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
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
import { SearchResults } from "./components/SearchResults";
import { SettingsView } from "./components/SettingsView";
import { api } from "./lib/api";
import { BOARD_STATUSES, OFF_BOARD_STATUSES, PIPELINE } from "./lib/types";
import { applyBoardFilters } from "./lib/filters";
import type { BoardFilters, Job, JobFilters, PipelineStatus } from "./lib/types";

export default function App() {
  const qc = useQueryClient();
  const [view, setViewState] = useState<View>("dashboard");
  const [filters, setFilters] = useState<JobFilters>({ sort: "recent" });
  // Dashboard-only client-side filters (Filters popup).
  const [boardFilters, setBoardFilters] = useState<BoardFilters>({});
  // Multi-select on the board (Gmail-style avatar checkboxes). anchorKey is the
  // last single-selected card, used as the start of a Shift+click range.
  const [selectedKeys, setSelectedKeys] = useState<Set<string>>(new Set());
  const [anchorKey, setAnchorKey] = useState<string | null>(null);
  const [selected, setSelected] = useState<Job | null>(null);
  // The drawer lives behind a lazy boundary; mount it on the first open and
  // keep it mounted so its slide-out (exit) animation still plays on close.
  const [drawerMounted, setDrawerMounted] = useState(false);
  useEffect(() => {
    if (selected) setDrawerMounted(true);
  }, [selected]);
  // The board card the user drilled into (full-screen focus view).
  const [focused, setFocused] = useState<Job | null>(null);
  const [activityOpen, setActivityOpen] = useState(false);
  // Off-canvas sidebar on mobile.
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Switching views always leaves the focus view, clears selection, and closes
  // the mobile nav.
  const setView = (v: View) => {
    setFocused(null);
    setSelectedKeys(new Set());
    setAnchorKey(null);
    setSidebarOpen(false);
    setViewState(v);
  };

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

  // Bulk actions over the multi-selected board cards (no delete here — that
  // only applies to already-skipped/mismatched jobs in the Inactive view).
  const bulkMove = useMutation({
    mutationFn: async (status: PipelineStatus) => {
      await Promise.all([...selectedKeys].map((k) => api.moveStatus(k, status)));
    },
    onSuccess: () => {
      refresh();
      clearSelection();
    },
  });
  const bulkSkip = useMutation({
    mutationFn: async () => {
      await Promise.all([...selectedKeys].map((k) => api.ignoreJob(k)));
    },
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
          mismatched: mismatchedCount,
          inactive: inactiveCount,
        }}
      />

      <main className="flex min-w-0 flex-1 flex-col overflow-hidden">
        {/* On mobile the focus view is purely the job detail, so hide the top
            bar (search, filters, Fetch alerts) there. */}
        <div className={focused ? "hidden md:block" : ""}>
          <TopBar
            onMenu={() => setSidebarOpen(true)}
            title={
              view === "dashboard"
                ? "Dashboard"
                : view === "mismatched"
                  ? "Mismatched jobs"
                  : view === "inactive"
                    ? "Inactive jobs"
                    : "Settings"
            }
            filters={filters}
            setFilters={setFilters}
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
              onOpen={setSelected}
              onToggleSelect={toggleSelect}
              onRangeSelect={selectRange}
              onClearSelection={clearSelection}
              anchorKey={anchorKey}
              selectedKeys={selectedKeys}
            />
          </div>
        ) : focused ? (
          <Suspense
            fallback={
              <div className="grid flex-1 place-items-center text-slate-400">Loading…</div>
            }
          >
            <FocusView
              jobs={visibleJobs}
              selected={focused}
              onSelect={setFocused}
              onBack={() => setFocused(null)}
              onChanged={() => {
                refresh();
                api.getJob(focused.job_key).then(setFocused).catch(() => {});
              }}
            />
          </Suspense>
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
                    onOpen={setFocused}
                    onIgnore={(j) => ignore.mutate(j.job_key)}
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

        {/* Multi-select action bar — shared by the board and search results
            (both are the dashboard view). Fixed-positioned, so it overlays
            whichever list is showing. */}
        {view === "dashboard" && selectedKeys.size > 0 && (
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
          <DrawerHost
            job={selected}
            onClose={() => setSelected(null)}
            onChanged={() => {
              if (!selected) return;
              refresh();
              // keep the drawer's job in sync after a status change
              api.getJob(selected.job_key).then(setSelected).catch(() => {});
            }}
          />
        </Suspense>
      )}

      <AgentChat />
    </div>
  );
}
