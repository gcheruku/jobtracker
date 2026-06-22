import { BOARD_STATUSES } from "../lib/types";
import { STATUS_STYLES } from "../lib/ui";
import type { Stats } from "../lib/types";

export function MetricCards({ stats }: { stats?: Stats }) {
  return (
    <div className="grid grid-cols-4 gap-2 sm:gap-3">
      {BOARD_STATUSES.map((s) => {
        const style = STATUS_STYLES[s];
        const count = stats?.by_status[s] ?? 0;
        return (
          <div
            key={s}
            className="rounded-lg border border-slate-200 bg-white px-2.5 py-2 shadow-sm"
          >
            <div className="flex items-center gap-1.5">
              <span className={`h-2 w-2 shrink-0 rounded-full ${style.dot}`} />
              <span className="truncate text-[11px] font-medium text-slate-500 sm:text-xs">
                {s}
              </span>
            </div>
            <div className="mt-0.5 text-lg font-semibold tracking-tight sm:text-2xl">
              {count}
            </div>
          </div>
        );
      })}
    </div>
  );
}
