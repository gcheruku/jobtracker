import {
  LayoutDashboard,
  Briefcase,
  Bookmark,
  Archive,
  FileText,
  Settings,
  SlidersHorizontal,
  Star,
  X,
} from "lucide-react";

export type View = "dashboard" | "watchlist" | "mismatched" | "inactive" | "settings";

const NAV: { id: View; label: string; icon: typeof LayoutDashboard }[] = [
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { id: "watchlist", label: "Watchlist", icon: Star },
  { id: "mismatched", label: "Mismatched", icon: SlidersHorizontal },
  { id: "inactive", label: "Inactive", icon: Archive },
  { id: "settings", label: "Settings", icon: Settings },
];

export function Sidebar({
  view,
  setView,
  counts,
  open = false,
  onClose,
}: {
  view: View;
  setView: (v: View) => void;
  counts: Partial<Record<View, number>>;
  open?: boolean;
  onClose?: () => void;
}) {
  return (
    <>
      {/* Backdrop on mobile when the drawer is open */}
      <div
        onClick={onClose}
        className={`fixed inset-0 z-30 bg-slate-900/40 transition-opacity md:hidden ${
          open ? "opacity-100" : "pointer-events-none opacity-0"
        }`}
      />

      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-60 shrink-0 transform flex-col border-r border-slate-200 bg-white transition-transform md:static md:translate-x-0 ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex items-center justify-between px-5 py-5">
          <div className="flex items-center gap-2">
            <div className="grid h-9 w-9 place-items-center rounded-xl bg-indigo-600 text-white">
              <Briefcase size={18} />
            </div>
            <span className="text-lg font-semibold tracking-tight">JobTrack</span>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-700 md:hidden"
          >
            <X size={20} />
          </button>
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
    </>
  );
}
