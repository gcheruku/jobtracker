import type { BoardFilters, Job } from "./types";

/**
 * Best-effort parse of a salary string's lower bound into a yearly number.
 * Handles "$150,000", "150k", "$150K - $180K". Returns null when no number is
 * found (those jobs are excluded while a salary filter is active).
 */
export function salaryFloor(salary: string | null): number | null {
  if (!salary) return null;
  const m = salary.replace(/,/g, "").match(/\$?\s*(\d+(?:\.\d+)?)\s*([kK])?/);
  if (!m) return null;
  let n = parseFloat(m[1]);
  if (m[2]) n *= 1000;
  return Math.round(n);
}

export function matchPct(job: Job): number | null {
  const v = job.llm_match_pct ?? job.match_pct;
  return v == null ? null : Math.round(v);
}

export function countActiveFilters(f: BoardFilters): number {
  return (f.workMode ? 1 : 0) + (f.salary ? 1 : 0) + (f.match ? 1 : 0);
}

export function applyBoardFilters(jobs: Job[], f: BoardFilters): Job[] {
  return jobs.filter((j) => {
    if (f.workMode) {
      const wm = j.work_mode;
      if (f.workMode.op === "is" && wm !== f.workMode.value) return false;
      if (f.workMode.op === "isNot" && wm === f.workMode.value) return false;
    }
    if (f.salary) {
      const s = salaryFloor(j.salary);
      if (s == null) return false;
      if (f.salary.op === "gte" && s < f.salary.value) return false;
      if (f.salary.op === "lte" && s > f.salary.value) return false;
    }
    if (f.match) {
      const m = matchPct(j);
      if (m == null) return false;
      if (f.match.op === "gte" && m < f.match.value) return false;
      if (f.match.op === "lte" && m > f.match.value) return false;
    }
    return true;
  });
}
