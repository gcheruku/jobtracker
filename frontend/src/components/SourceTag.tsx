const COLORS: Record<string, string> = {
  LinkedIn: "bg-sky-50 text-sky-700",
  Indeed: "bg-indigo-50 text-indigo-700",
  Glassdoor: "bg-emerald-50 text-emerald-700",
  Dice: "bg-rose-50 text-rose-700",
  Manual: "bg-slate-100 text-slate-600",
};

/** Small chip showing where a job came from (Indeed/Glassdoor/LinkedIn/…). */
export function SourceTag({ source }: { source: string | null }) {
  if (!source) return null;
  const cls = COLORS[source] ?? "bg-slate-100 text-slate-600";
  return (
    <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${cls}`}>
      {source}
    </span>
  );
}
