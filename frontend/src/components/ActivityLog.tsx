import { useQuery } from "@tanstack/react-query";
import { Activity, ChevronRight } from "lucide-react";
import { api } from "../lib/api";
import { STATUS_STYLES, initials, timeAgo } from "../lib/ui";
import type { PipelineStatus } from "../lib/types";

export function ActivityLog({ onCollapse }: { onCollapse?: () => void }) {
  const activity = useQuery({ queryKey: ["activity"], queryFn: api.activity });
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Activity size={16} className="text-indigo-600" />
          <h3 className="text-sm font-semibold">Recent activity</h3>
        </div>
        {onCollapse && (
          <button
            onClick={onCollapse}
            title="Collapse"
            className="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
          >
            <ChevronRight size={16} />
          </button>
        )}
      </div>
      <ul className="space-y-3">
        {activity.data?.map((a) => {
          const style = STATUS_STYLES[a.status as PipelineStatus];
          return (
            <li key={a.job_key + a.at} className="flex items-center gap-3">
              <div className="grid h-8 w-8 shrink-0 place-items-center rounded-md bg-slate-100 text-[10px] font-bold text-slate-600">
                {initials(a.company)}
              </div>
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-medium">{a.title}</div>
                <div className="truncate text-xs text-slate-400">{a.company}</div>
              </div>
              <div className="text-right">
                <span
                  className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${
                    style?.chip ?? "bg-slate-100 text-slate-500"
                  }`}
                >
                  {a.status}
                </span>
                <div className="text-[11px] text-slate-400">{timeAgo(a.at)}</div>
              </div>
            </li>
          );
        })}
        {activity.data?.length === 0 && (
          <li className="text-xs text-slate-400">No activity yet.</li>
        )}
      </ul>
    </div>
  );
}
