import {
  LayoutDashboard,
  Briefcase,
  Bookmark,
  Archive,
  FileText,
  Settings,
} from "lucide-react";

export type View = "dashboard" | "inactive";

const NAV: { id: View; label: string; icon: typeof LayoutDashboard }[] = [
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { id: "inactive", label: "Inactive", icon: Archive },
];

export function Sidebar({
  view,
  setView,
  counts,
}: {
  view: View;
  setView: (v: View) => void;
  counts: Partial<Record<View, number>>;
}) {
  return (
    <aside className="flex w-60 shrink-0 flex-col border-r border-slate-200 bg-white">
      <div className="flex items-center gap-2 px-5 py-5">
        <div className="grid h-9 w-9 place-items-center rounded-xl bg-indigo-600 text-white">
          <Briefcase size={18} />
        </div>
        <span className="text-lg font-semibold tracking-tight">JobTrack</span>
      </div>

      <nav className="flex-1 px-3">
        {NAV.map(({ id, label, icon: Icon }) => {
          const active = view === id;
          return (
            <button
              key={id}
              onClick={() => setView(id)}
              className={`mb-1 flex w-full items-center justify-between rounded-lg px-3 py-2 text-sm font-medium transition ${
                active
                  ? "bg-indigo-50 text-indigo-700"
                  : "text-slate-600 hover:bg-slate-50"
              }`}
            >
              <span className="flex items-center gap-3">
                <Icon size={18} />
                {label}
              </span>
              {counts[id] != null && counts[id]! > 0 && (
                <span className="rounded-full bg-slate-200 px-2 text-xs text-slate-600">
                  {counts[id]}
                </span>
              )}
            </button>
          );
        })}

        <div className="mt-4 space-y-1 px-1 text-sm text-slate-400">
          {[
            { label: "Applications", icon: Briefcase },
            { label: "Saved", icon: Bookmark },
            { label: "Resume", icon: FileText },
            { label: "Settings", icon: Settings },
          ].map(({ label, icon: Icon }) => (
            <div
              key={label}
              className="flex cursor-not-allowed items-center gap-3 rounded-lg px-3 py-2"
              title="Coming soon"
            >
              <Icon size={18} />
              {label}
            </div>
          ))}
        </div>
      </nav>

      <div className="m-3 flex items-center gap-3 rounded-xl border border-slate-200 p-3">
        <div className="grid h-9 w-9 place-items-center rounded-full bg-slate-800 text-sm font-semibold text-white">
          JT
        </div>
        <div className="leading-tight">
          <div className="text-sm font-medium">Job Seeker</div>
          <div className="text-xs text-slate-400">Self-hosted</div>
        </div>
      </div>
    </aside>
  );
}
