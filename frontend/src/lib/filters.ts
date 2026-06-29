import type { BoardFilters, Job } from "./types";

/**
 * Best-effort parse of a salary string into its low/high bounds.
 * Handles "$150,000", "150k", "$50K - $180K". Returns null when no number is
 * found (those jobs are excluded while a salary filter is active).
 */
export function salaryRange(salary: string | null): { lo: number; hi: number } | null {
  if (!salary) return null;
  const re = /(\d+(?:\.\d+)?)\s*([kK])?/g;
  const nums: number[] = [];
  let m: RegExpExecArray | null;
  while ((m = re.exec(salary.replace(/,/g, ""))) !== null) {
    let n = parseFloat(m[1]);
    if (m[2]) n *= 1000;
    nums.push(Math.round(n));
  }
  if (nums.length === 0) return null;
  return { lo: Math.min(...nums), hi: Math.max(...nums) };
}

export function matchPct(job: Job): number | null {
  const v = job.llm_match_pct ?? job.match_pct;
  return v == null ? null : Math.round(v);
}

export function countActiveFilters(f: BoardFilters): number {
  return (
    (f.workMode ? 1 : 0) +
    (f.salary ? 1 : 0) +
    (f.match ? 1 : 0) +
    (f.distance ? 1 : 0)
  );
}

export function applyBoardFilters(jobs: Job[], f: BoardFilters): Job[] {
  return jobs.filter((j) => {
    if (f.workMode) {
      const wm = j.work_mode;
      if (f.workMode.op === "is" && wm !== f.workMode.value) return false;
      if (f.workMode.op === "isNot" && wm === f.workMode.value) return false;
    }
    if (f.salary) {
      const r = salaryRange(j.salary);
      if (r == null) return false;
      // "at least X": the lower bound must clear X.
      // "at most X": the upper bound must stay within X.
      if (f.salary.op === "gte" && r.lo < f.salary.value) return false;
      if (f.salary.op === "lte" && r.hi > f.salary.value) return false;
    }
    if (f.match) {
      const m = matchPct(j);
      if (m == null) return false;
      if (f.match.op === "gte" && m < f.match.value) return false;
      if (f.match.op === "lte" && m > f.match.value) return false;
    }
    if (f.distance) {
      const d = j.distance_miles;
      if (d == null) return false; // remote / unknown excluded when filtering
      if (f.distance.op === "gte" && d < f.distance.value) return false;
      if (f.distance.op === "lte" && d > f.distance.value) return false;
    }
    return true;
  });
}
