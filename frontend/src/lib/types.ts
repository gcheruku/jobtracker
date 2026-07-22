export type PipelineStatus =
  | "Saved"
  | "Applied"
  | "Interviewing"
  | "Offer"
  | "Rejected"
  | "Expired";

// All statuses (move targets in the drawer).
export const PIPELINE: PipelineStatus[] = [
  "Saved",
  "Applied",
  "Interviewing",
  "Offer",
  "Rejected",
  "Expired",
];

// Columns shown on the active board.
export const BOARD_STATUSES: PipelineStatus[] = [
  "Saved",
  "Applied",
  "Interviewing",
  "Offer",
];

// Statuses kept off the board (shown in the Inactive view alongside skipped jobs).
export const OFF_BOARD_STATUSES: PipelineStatus[] = ["Rejected", "Expired"];

export interface Job {
  job_key: string;
  title: string | null;
  company: string | null;
  location: string | null;
  url: string | null;
  salary: string | null;
  work_mode: string | null;
  distance_miles: number | null;
  source: string | null;
  status: PipelineStatus;
  raw_status: string | null;
  match_pct: number | null;
  llm_match_pct: number | null;
  semantic_score: number | null;
  compare_score: number | null;
  compare_at: string | null;
  job_description: string | null;
  email_date: string | null;
  status_updated_at: string | null;
  ignored: boolean;
  mismatched: boolean;
  mismatch_reason: string | null;
  watchlist: boolean;
  // The company's candidate-portal home page. Stored per-company: set it on one
  // job and every job at the same company shares it.
  portal_url: string | null;
}

export interface Stats {
  total: number;
  visible: number;
  ignored: number;
  mismatched: number;
  watchlist: number;
  by_status: Record<string, number>;
}

export interface Settings {
  city: string;
  max_distance_miles: number | null;
  salary_min: number | null;
  salary_max: number | null;
  min_match_score: number | null;
  title_keywords: string[];
  exclude_companies: string[];
  agent_provider: string | null;
}

export interface SemanticStatus {
  running: boolean;
  total: number;
  done: number;
  scored: number;
  no_jd: number;
  expired: number;
  eligible: number;
  available: boolean;
  last_error: string | null;
  last_run_iso: string | null;
}

export interface ApplyStatus {
  running: boolean;
  last_summary: {
    evaluated: number;
    moved_to_mismatched: number;
    restored: number;
    still_mismatched: number;
    geocode_failures: number;
  } | null;
  last_error: string | null;
  last_run_iso: string | null;
}

export interface Note {
  id: number;
  job_key: string;
  content: string;
  created_at: string;
  updated_at: string;
}

export interface ChecklistItem {
  id: number;
  job_key: string;
  text: string;
  done: boolean;
  position: number;
}

export interface CompareResult {
  job_key: string;
  match_score: number;
  report_markdown: string;
  used_job_description: boolean;
  model: string;
  source: string;
  created_at: string;
  cached: boolean;
}

export interface AiModels {
  enabled: boolean;
  default: string;
  models: string[];
}

export interface Resume {
  id: number;
  name: string;
  content_text: string;
  file_name: string | null;
  mime_type: string | null;
  is_active: boolean;
  uploaded_at: string;
}

export interface IngestSummary {
  emails_scanned: number;
  jobs_found: number;
  new_jobs: number;
  duplicates: number;
  scored: number;
  watermark_advanced_to?: string;
}

export interface IngestStatus {
  running: boolean;
  phase?: string;              // "starting" | "scoring" | …
  scored_so_far?: number;      // live count during a run
  last_run_iso: string | null;
  last_summary: IngestSummary | null;
  last_error: string | null;
  label: string;
  interval_hours: number;
  gemini_enabled: boolean;
}

export interface JobFilters {
  q?: string;
  // How `q` is matched: every word (default), any word, or exact whole-word phrase.
  match?: "all" | "any" | "phrase";
  status?: string;
  work_mode?: string;
  min_salary?: number;
  sort?: string;
  only_ignored?: boolean;
  include_ignored?: boolean;
  board_only?: boolean;
  off_board?: boolean;
  only_mismatched?: boolean;
  watchlist?: boolean;
  // Search "hide handled" toggle: drop jobs you've already triaged — both
  // watchlisted (starred) and in-pipeline (Applied/Interviewing/Offer) — leaving
  // only the untouched Saved candidate pool. The two flags always move together.
  hide_watchlist?: boolean;
  hide_pipeline?: boolean;
}

// Client-side dashboard filters set via the Filters popup. Each field carries
// an operator so you can filter jobs IN or OUT (e.g. salary >= or <=, work
// mode is / is not). Applied over the already-loaded board jobs.
export interface BoardFilters {
  workMode?: { op: "is" | "isNot"; value: string };
  salary?: { op: "gte" | "lte"; value: number };
  match?: { op: "gte" | "lte"; value: number };
  distance?: { op: "gte" | "lte"; value: number };
}
