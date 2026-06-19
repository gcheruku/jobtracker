import { BOARD_STATUSES } from "../lib/types";
import { STATUS_STYLES } from "../lib/ui";
import type { Stats } from "../lib/types";

export function MetricCards({ stats }: { stats?: Stats }) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {BOARD_STATUSES.map((s) => {
        const style = STATUS_STYLES[s];
        const count = stats?.by_status[s] ?? 0;
        return (
          <div
            key={s}
            className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm"
          >
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-slate-500">{s}</span>
              <span className={`h-2.5 w-2.5 rounded-full ${style.dot}`} />
            </div>
            <div className="mt-2 text-3xl font-semibold tracking-tight">
              {count}
            </div>
          </div>
        );
      })}
    </div>
  );
}
