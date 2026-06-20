import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence } from "framer-motion";
import { Activity } from "lucide-react";
import { Sidebar, type View } from "./components/Sidebar";
import { TopBar } from "./components/TopBar";
import { MetricCards } from "./components/MetricCards";
import { KanbanBoard } from "./components/KanbanBoard";
import { JobDrawer } from "./components/JobDrawer";
import { ActivityLog } from "./components/ActivityLog";
import { InactiveView } from "./components/InactiveView";
import { SearchResults } from "./components/SearchResults";
import { SettingsView } from "./components/SettingsView";
import { api } from "./lib/api";
import { BOARD_STATUSES, OFF_BOARD_STATUSES } from "./lib/types";
import type { Job, JobFilters, PipelineStatus } from "./lib/types";

export default function App() {
  const qc = useQueryClient();
  const [view, setView] = useState<View>("dashboard");
  const [filters, setFilters] = useState<JobFilters>({ sort: "recent" });
  const [selected, setSelected] = useState<Job | null>(null);
  const [activityOpen, setActivityOpen] = useState(false);

  const jobs = useQuery({
    queryKey: ["jobs", "board", filters],
    queryFn: () => api.listJobs({ ...filters, board_only: true }),
  });
  const stats = useQuery({ queryKey: ["stats"], queryFn: api.stats });

  const searching = (filters.q ?? "").trim() !== "";
  const byStatus = stats.data?.by_status ?? {};
  const boardTotal = BOARD_STATUSES.reduce((n, s) => n + (byStatus[s] ?? 0), 0);
  const inactiveCount =
    (stats.data?.ignored ?? 0) +
    (stats.data?.mismatched ?? 0) +
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
        counts={{ dashboard: boardTotal, inactive: inactiveCount }}
      />

      <main className="flex flex-1 flex-col overflow-hidden">
        <TopBar
          title={
            view === "dashboard" ? "Dashboard" : view === "inactive" ? "Inactive jobs" : "Settings"
          }
          filters={filters}
          setFilters={setFilters}
        />

        {view === "settings" ? (
          <div className="flex-1 overflow-y-auto">
            <SettingsView />
          </div>
        ) : view === "inactive" ? (
          <div className="flex-1 overflow-y-auto">
            <InactiveView filters={filters} />
          </div>
        ) : searching ? (
          <div className="flex-1 overflow-y-auto">
            <SearchResults filters={filters} onOpen={setSelected} />
          </div>
        ) : (
          <div className="flex-1 overflow-y-auto p-6">
            <MetricCards stats={stats.data} />

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
                    onOpen={setSelected}
                    onIgnore={(j) => ignore.mutate(j.job_key)}
                    onMove={(key, status) => move.mutate({ key, status })}
                  />
                )}
              </div>

              {activityOpen && (
                <div className="space-y-6">
                  <ActivityLog onCollapse={() => setActivityOpen(false)} />
                </div>
              )}
            </div>
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
