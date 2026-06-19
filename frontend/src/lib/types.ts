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
  source: string | null;
  status: PipelineStatus;
  raw_status: string | null;
  match_pct: number | null;
  llm_match_pct: number | null;
  job_description: string | null;
  email_date: string | null;
  status_updated_at: string | null;
  ignored: boolean;
}

export interface Stats {
  total: number;
  visible: number;
  ignored: number;
  by_status: Record<string, number>;
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

export interface KeywordChip {
  label: string;
  matched: boolean;
}

export interface CompareResult {
  job_key: string;
  match_score: number;
  matched_keywords: string[];
  missing_keywords: string[];
  keyword_chips: KeywordChip[];
  interview_questions: string[];
  resume_tips: string[];
  summary: string;
  source: string;
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

export interface JobFilters {
  q?: string;
  status?: string;
  work_mode?: string;
  min_salary?: number;
  sort?: string;
  only_ignored?: boolean;
  board_only?: boolean;
  off_board?: boolean;
}
