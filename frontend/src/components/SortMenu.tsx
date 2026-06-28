import { useState } from "react";
import { ArrowUpDown, Check } from "lucide-react";

const SORTS = [
  { v: "recent", label: "Most recent" },
  { v: "semantic", label: "Semantic match" },
  { v: "match", label: "Best match (AI)" },
  { v: "company", label: "Company A–Z" },
  { v: "title", label: "Title A–Z" },
];

/**
 * Compact sort control: an icon button (icon-only on mobile, with the current
 * sort label on desktop) that opens a dropdown menu of sort options.
 */
export function SortMenu({
  value,
  onChange,
}: {
  value: string;
  onChange: (v: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const current = SORTS.find((s) => s.v === value) ?? SORTS[0];

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        title="Sort"
        className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-600 hover:bg-slate-50"
      >
        <ArrowUpDown size={15} className="text-slate-400" />
        <span className="hidden sm:inline">{current.label}</span>
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-30" onClick={() => setOpen(false)} />
          <div className="absolute right-0 z-40 mt-2 w-44 overflow-hidden rounded-lg border border-slate-200 bg-white py-1 shadow-lg">
            {SORTS.map((s) => (
              <button
                key={s.v}
                onClick={() => {
                  onChange(s.v);
                  setOpen(false);
                }}
                className={`flex w-full items-center justify-between px-3 py-2 text-left text-sm hover:bg-slate-50 ${
                  s.v === value ? "font-medium text-indigo-700" : "text-slate-600"
                }`}
              >
                {s.label}
                {s.v === value && <Check size={15} className="text-indigo-600" />}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
