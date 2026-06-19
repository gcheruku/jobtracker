import type { PipelineStatus } from "./types";

export const STATUS_STYLES: Record<
  PipelineStatus,
  { dot: string; bar: string; chip: string; text: string }
> = {
  Saved: { dot: "bg-indigo-500", bar: "bg-indigo-500", chip: "bg-indigo-50 text-indigo-700", text: "text-indigo-600" },
  Applied: { dot: "bg-sky-500", bar: "bg-sky-500", chip: "bg-sky-50 text-sky-700", text: "text-sky-600" },
  Interviewing: { dot: "bg-amber-500", bar: "bg-amber-500", chip: "bg-amber-50 text-amber-700", text: "text-amber-600" },
  Offer: { dot: "bg-emerald-500", bar: "bg-emerald-500", chip: "bg-emerald-50 text-emerald-700", text: "text-emerald-600" },
  Rejected: { dot: "bg-rose-500", bar: "bg-rose-500", chip: "bg-rose-50 text-rose-700", text: "text-rose-600" },
  Expired: { dot: "bg-slate-400", bar: "bg-slate-400", chip: "bg-slate-100 text-slate-600", text: "text-slate-500" },
};

export function initials(company: string | null): string {
  if (!company) return "?";
  return company
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? "")
    .join("");
}

export function timeAgo(iso: string | null): string {
  if (!iso) return "";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const diff = Date.now() - then;
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days < 30) return `${days}d ago`;
  return new Date(iso).toLocaleDateString();
}
