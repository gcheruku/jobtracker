import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence } from "framer-motion";
import { Activity, X } from "lucide-react";
import { Sidebar, type View } from "./components/Sidebar";
import { TopBar } from "./components/TopBar";
import { MetricCards } from "./components/MetricCards";
import { KanbanBoard } from "./components/KanbanBoard";
import { FocusView } from "./components/FocusView";
import { JobDrawer } from "./components/JobDrawer";
import { ActivityLog } from "./components/ActivityLog";
import { InactiveView } from "./components/InactiveView";
import { MismatchedView } from "./components/MismatchedView";
import { SearchResults } from "./components/SearchResults";
import { SettingsView } from "./components/SettingsView";
import { api } from "./lib/api";
import { BOARD_STATUSES, OFF_BOARD_STATUSES } from "./lib/types";
import type { Job, JobFilters, PipelineStatus } from "./lib/types";

export default function App() {
  const qc = useQueryClient();
  const [view, setViewState] = useState<View>("dashboard");
  const [filters, setFilters] = useState<JobFilters>({ sort: "recent" });
  const [selected, setSelected] = useState<Job | null>(null);
  // The board card the user drilled into (full-screen focus view).
  const [focused, setFocused] = useState<Job | null>(null);
  const [activityOpen, setActivityOpen] = useState(false);
  // Off-canvas sidebar on mobile.
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Switching views always leaves the focus view and closes the mobile nav.
  const setView = (v: View) => {
    setFocused(null);
    setSidebarOpen(false);
    setViewState(v);
  };

  const jobs = useQuery({
    queryKey: ["jobs", "board", filters],
    queryFn: () => api.listJobs({ ...filters, board_only: true }),
  });
  const stats = useQuery({ queryKey: ["stats"], queryFn: api.stats });

  const searching = (filters.q ?? "").trim() !== "";
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
          <div className="flex-1 overflow-y-auto">
            <SearchResults filters={filters} onOpen={setSelected} />
          </div>
        ) : focused ? (
          <FocusView
            jobs={jobs.data ?? []}
            selected={focused}
            onSelect={setFocused}
            onBack={() => setFocused(null)}
            onChanged={() => {
              refresh();
              api.getJob(focused.job_key).then(setFocused).catch(() => {});
            }}
          />
        ) : (
          // No top padding here: the sticky column dropdown pins flush against
          // the top bar (top padding would leave a strip where cards show
          // through while scrolling). The top gap moves onto MetricCards.
          <div className="flex-1 overflow-y-auto px-4 pb-4 sm:px-6 sm:pb-6">
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
                      {jobs.data?.length ?? 0} shown · {boardTotal} active
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
                    jobs={jobs.data ?? []}
                    onOpen={setFocused}
                    onIgnore={(j) => ignore.mutate(j.job_key)}
                    onMove={(key, status) => move.mutate({ key, status })}
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
      </main>

      <AnimatePresence>
        {selected && (
          <JobDrawer
            key={selected.job_key}
            job={selected}
            onClose={() => setSelected(null)}
            onChanged={() => {
              refresh();
              // keep the drawer's job in sync after a status change
              api.getJob(selected.job_key).then(setSelected).catch(() => {});
            }}
          />
        )}
      </AnimatePresence>
    </div>
  );
}
