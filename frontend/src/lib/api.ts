import type {
  AiModels,
  ApplyStatus,
  ChecklistItem,
  CompareResult,
  IngestStatus,
  Job,
  JobFilters,
  Note,
  Resume,
  SemanticStatus,
  Settings,
  Stats,
} from "./types";

// In dev, requests hit Vite's proxy (/api -> :8000). In a static prod build set
// VITE_API_BASE to the backend URL (e.g. http://my-server:8000).
const BASE = import.meta.env.VITE_API_BASE ?? "";

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`${res.status} ${detail}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

const key = (k: string) => encodeURIComponent(k);

export const api = {
  // --- jobs ---
  listJobs(filters: JobFilters = {}): Promise<Job[]> {
    const p = new URLSearchParams();
    if (filters.q) p.set("q", filters.q);
    if (filters.status) p.set("status", filters.status);
    if (filters.work_mode) p.set("work_mode", filters.work_mode);
    if (filters.min_salary) p.set("min_salary", String(filters.min_salary));
    if (filters.sort) p.set("sort", filters.sort);
    if (filters.only_ignored) p.set("only_ignored", "true");
    if (filters.include_ignored) p.set("include_ignored", "true");
    if (filters.board_only) p.set("board_only", "true");
    if (filters.off_board) p.set("off_board", "true");
    if (filters.only_mismatched) p.set("only_mismatched", "true");
    return http<Job[]>(`/api/jobs?${p.toString()}`);
  },
  getJob(k: string): Promise<Job> {
    return http<Job>(`/api/jobs/${key(k)}`);
  },
  createJob(body: Partial<Job>): Promise<Job> {
    return http<Job>(`/api/jobs`, { method: "POST", body: JSON.stringify(body) });
  },
  updateJob(k: string, body: Partial<Job>): Promise<Job> {
    return http<Job>(`/api/jobs/${key(k)}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    });
  },
  moveStatus(k: string, status: string): Promise<Job> {
    return http<Job>(`/api/jobs/${key(k)}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    });
  },
  ignoreJob(k: string): Promise<Job> {
    return http<Job>(`/api/jobs/${key(k)}/ignore`, { method: "POST" });
  },
  restoreJob(k: string): Promise<Job> {
    return http<Job>(`/api/jobs/${key(k)}/restore`, { method: "POST" });
  },
  deleteJob(k: string): Promise<void> {
    return http<void>(`/api/jobs/${key(k)}`, { method: "DELETE" });
  },
  bulkRestore(keys: string[]): Promise<{ restored: number }> {
    return http(`/api/jobs/bulk-restore`, {
      method: "POST",
      body: JSON.stringify({ job_keys: keys }),
    });
  },
  bulkDelete(keys: string[]): Promise<{ deleted: number }> {
    return http(`/api/jobs/bulk-delete`, {
      method: "POST",
      body: JSON.stringify({ job_keys: keys }),
    });
  },

  // --- stats / activity ---
  stats(): Promise<Stats> {
    return http<Stats>(`/api/stats`);
  },
  activity(): Promise<
    { job_key: string; title: string; company: string; status: string; at: string }[]
  > {
    return http(`/api/stats/activity?limit=12`);
  },

  // --- notes ---
  listNotes(k: string): Promise<Note[]> {
    return http<Note[]>(`/api/jobs/${key(k)}/notes`);
  },
  addNote(k: string, content: string): Promise<Note> {
    return http<Note>(`/api/jobs/${key(k)}/notes`, {
      method: "POST",
      body: JSON.stringify({ content }),
    });
  },
  deleteNote(id: number): Promise<void> {
    return http<void>(`/api/jobs/notes/${id}`, { method: "DELETE" });
  },

  // --- checklist ---
  listChecklist(k: string): Promise<ChecklistItem[]> {
    return http<ChecklistItem[]>(`/api/jobs/${key(k)}/checklist`);
  },
  addChecklistItem(k: string, text: string): Promise<ChecklistItem> {
    return http<ChecklistItem>(`/api/jobs/${key(k)}/checklist`, {
      method: "POST",
      body: JSON.stringify({ text }),
    });
  },
  toggleChecklistItem(id: number, done: boolean): Promise<ChecklistItem> {
    return http<ChecklistItem>(`/api/jobs/checklist/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ done }),
    });
  },
  deleteChecklistItem(id: number): Promise<void> {
    return http<void>(`/api/jobs/checklist/${id}`, { method: "DELETE" });
  },

  // --- resume ---
  listResumes(): Promise<Resume[]> {
    return http<Resume[]>(`/api/resumes`);
  },
  activeResume(): Promise<Resume | null> {
    return http<Resume | null>(`/api/resumes/active`);
  },
  saveResumeText(name: string, content_text: string): Promise<Resume> {
    return http<Resume>(`/api/resumes/text`, {
      method: "POST",
      body: JSON.stringify({ name, content_text }),
    });
  },

  // --- settings / preferences ---
  getSettings(): Promise<Settings> {
    return http<Settings>(`/api/settings`);
  },
  saveSettings(s: Settings): Promise<Settings> {
    return http<Settings>(`/api/settings`, { method: "PUT", body: JSON.stringify(s) });
  },
  applySettings(): Promise<{ started: boolean; detail?: string }> {
    return http(`/api/settings/apply`, { method: "POST" });
  },
  applyStatus(): Promise<ApplyStatus> {
    return http<ApplyStatus>(`/api/settings/apply-status`);
  },

  // --- semantic matching ---
  semanticStatus(): Promise<SemanticStatus> {
    return http<SemanticStatus>(`/api/semantic/status`);
  },
  runSemantic(recheck = false): Promise<{ started: boolean; detail?: string }> {
    return http(`/api/semantic/run${recheck ? "?recheck=true" : ""}`, {
      method: "POST",
    });
  },

  // --- gmail ingest ---
  ingestRun(opts?: {
    since_epoch?: number;
    fetch_all?: boolean;
  }): Promise<{ started: boolean; detail?: string }> {
    const p = new URLSearchParams();
    if (opts?.fetch_all) p.set("fetch_all", "true");
    if (opts?.since_epoch != null) p.set("since_epoch", String(opts.since_epoch));
    const qs = p.toString();
    return http(`/api/ingest/run${qs ? `?${qs}` : ""}`, { method: "POST" });
  },
  ingestStatus(): Promise<IngestStatus> {
    return http<IngestStatus>(`/api/ingest/status`);
  },

  // --- ai compare ---
  aiModels(): Promise<AiModels> {
    return http<AiModels>(`/api/ai/models`);
  },
  getCompare(k: string): Promise<CompareResult | null> {
    return http<CompareResult | null>(`/api/ai/compare/${key(k)}`);
  },
  runCompare(
    k: string,
    opts: { force?: boolean; model?: string } = {}
  ): Promise<CompareResult> {
    return http<CompareResult>(`/api/ai/compare/${key(k)}`, {
      method: "POST",
      body: JSON.stringify(opts),
    });
  },
};
