import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  X,
  ExternalLink,
  MapPin,
  Briefcase,
  DollarSign,
  Sparkles,
  Plus,
  Trash2,
  EyeOff,
} from "lucide-react";
import { api } from "../lib/api";
import { PIPELINE, type Job, type PipelineStatus } from "../lib/types";
import { STATUS_STYLES, timeAgo } from "../lib/ui";
import { ComparePanel } from "./ComparePanel";

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="border-t border-slate-100 px-5 py-4">
      <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
        {title}
      </h4>
      {children}
    </section>
  );
}

export function JobDrawer({
  job,
  onClose,
  onChanged,
}: {
  job: Job;
  onClose: () => void;
  onChanged: () => void;
}) {
  const qc = useQueryClient();
  const [showCompare, setShowCompare] = useState(false);
  const [noteText, setNoteText] = useState("");
  const [taskText, setTaskText] = useState("");

  const notes = useQuery({
    queryKey: ["notes", job.job_key],
    queryFn: () => api.listNotes(job.job_key),
  });
  const checklist = useQuery({
    queryKey: ["checklist", job.job_key],
    queryFn: () => api.listChecklist(job.job_key),
  });

  const invalidate = (k: string) =>
    qc.invalidateQueries({ queryKey: [k, job.job_key] });

  const addNote = useMutation({
    mutationFn: () => api.addNote(job.job_key, noteText),
    onSuccess: () => {
      setNoteText("");
      invalidate("notes");
    },
  });
  const delNote = useMutation({
    mutationFn: (id: number) => api.deleteNote(id),
    onSuccess: () => invalidate("notes"),
  });
  const addTask = useMutation({
    mutationFn: () => api.addChecklistItem(job.job_key, taskText),
    onSuccess: () => {
      setTaskText("");
      invalidate("checklist");
    },
  });
  const toggleTask = useMutation({
    mutationFn: (v: { id: number; done: boolean }) =>
      api.toggleChecklistItem(v.id, v.done),
    onSuccess: () => invalidate("checklist"),
  });
  const delTask = useMutation({
    mutationFn: (id: number) => api.deleteChecklistItem(id),
    onSuccess: () => invalidate("checklist"),
  });
  const move = useMutation({
    mutationFn: (status: PipelineStatus) => api.moveStatus(job.job_key, status),
    onSuccess: onChanged,
  });
  const ignore = useMutation({
    mutationFn: () => api.ignoreJob(job.job_key),
    onSuccess: () => {
      // Refresh the board/stats but DON'T call onChanged() — it re-fetches this
      // job and would re-open the drawer right after we close it.
      qc.invalidateQueries({ queryKey: ["jobs"] });
      qc.invalidateQueries({ queryKey: ["stats"] });
      qc.invalidateQueries({ queryKey: ["activity"] });
      onClose();
    },
  });

  return (
    <div className="fixed inset-0 z-30 flex justify-end">
      <div className="absolute inset-0 bg-slate-900/30" onClick={onClose} />
      <motion.aside
        initial={{ x: 480 }}
        animate={{ x: 0 }}
        exit={{ x: 480 }}
        transition={{ type: "spring", damping: 28, stiffness: 280 }}
        className="relative flex h-full w-full max-w-md flex-col overflow-hidden bg-white shadow-2xl"
      >
        {showCompare && (
          <ComparePanel job={job} onClose={() => setShowCompare(false)} />
        )}

        {/* Header */}
        <div className="flex items-start justify-between px-5 py-5">
          <div className="min-w-0 pr-3">
            <h2 className="text-lg font-semibold leading-tight">
              {job.title || "Untitled role"}
            </h2>
            <p className="text-sm text-slate-500">{job.company}</p>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-700">
            <X size={20} />
          </button>
        </div>

        {/* Primary action */}
        <div className="px-5 pb-4">
          <button
            onClick={() => setShowCompare(true)}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-indigo-600 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-indigo-700"
          >
            <Sparkles size={16} />
            Compare with Resume
          </button>
        </div>

        <div className="flex-1 overflow-y-auto thin-scroll">
          {/* Pipeline status picker */}
          <Section title="Pipeline status">
            <div className="flex flex-wrap gap-1.5">
              {PIPELINE.map((s) => {
                const active = job.status === s;
                const style = STATUS_STYLES[s];
                return (
                  <button
                    key={s}
                    onClick={() => move.mutate(s)}
                    className={`rounded-full px-3 py-1 text-xs font-medium transition ${
                      active ? style.chip + " ring-1 ring-current" : "bg-slate-100 text-slate-500 hover:bg-slate-200"
                    }`}
                  >
                    {s}
                  </button>
                );
              })}
            </div>
          </Section>

          {/* Metadata */}
          <Section title="Details">
            <dl className="space-y-2 text-sm">
              {job.location && (
                <div className="flex items-center gap-2 text-slate-600">
                  <MapPin size={15} className="text-slate-400" /> {job.location}
                </div>
              )}
              {job.work_mode && (
                <div className="flex items-center gap-2 text-slate-600">
                  <Briefcase size={15} className="text-slate-400" /> {job.work_mode}
                </div>
              )}
              {job.salary && (
                <div className="flex items-center gap-2 text-emerald-600">
                  <DollarSign size={15} /> {job.salary}
                </div>
              )}
              {(job.llm_match_pct ?? job.match_pct) != null && (
                <div className="flex items-center gap-2 text-slate-600">
                  <Sparkles size={15} className="text-indigo-400" />
                  Stored match: {Math.round(job.llm_match_pct ?? job.match_pct!)}%
                </div>
              )}
              {job.url && (
                <a
                  href={job.url}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center gap-2 text-indigo-600 hover:underline"
                >
                  <ExternalLink size={15} /> View original posting
                </a>
              )}
            </dl>
          </Section>

          {/* Description */}
          {job.job_description && (
            <Section title="Job description">
              <p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-600">
                {job.job_description.slice(0, 4000)}
              </p>
            </Section>
          )}

          {/* Notes */}
          <Section title="Personal notes">
            <div className="mb-2 flex gap-2">
              <input
                value={noteText}
                onChange={(e) => setNoteText(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && noteText && addNote.mutate()}
                placeholder="Add a note…"
                className="flex-1 rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-indigo-400"
              />
              <button
                onClick={() => noteText && addNote.mutate()}
                className="rounded-lg bg-slate-800 px-3 text-white"
              >
                <Plus size={16} />
              </button>
            </div>
            <ul className="space-y-2">
              {notes.data?.map((n) => (
                <li
                  key={n.id}
                  className="group flex items-start justify-between gap-2 rounded-lg bg-amber-50 px-3 py-2 text-sm text-slate-700"
                >
                  <span className="whitespace-pre-wrap">{n.content}</span>
                  <button
                    onClick={() => delNote.mutate(n.id)}
                    className="opacity-0 transition group-hover:opacity-100"
                  >
                    <Trash2 size={14} className="text-slate-400 hover:text-rose-500" />
                  </button>
                </li>
              ))}
              {notes.data?.length === 0 && (
                <li className="text-xs text-slate-400">No notes yet.</li>
              )}
            </ul>
          </Section>

          {/* Checklist */}
          <Section title="Action items">
            <div className="mb-2 flex gap-2">
              <input
                value={taskText}
                onChange={(e) => setTaskText(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && taskText && addTask.mutate()}
                placeholder="Add a task…"
                className="flex-1 rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-indigo-400"
              />
              <button
                onClick={() => taskText && addTask.mutate()}
                className="rounded-lg bg-slate-800 px-3 text-white"
              >
                <Plus size={16} />
              </button>
            </div>
            <ul className="space-y-1.5">
              {checklist.data?.map((item) => (
                <li key={item.id} className="group flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={item.done}
                    onChange={() =>
                      toggleTask.mutate({ id: item.id, done: !item.done })
                    }
                    className="h-4 w-4 rounded border-slate-300 text-indigo-600"
                  />
                  <span
                    className={
                      item.done ? "flex-1 text-slate-400 line-through" : "flex-1 text-slate-700"
                    }
                  >
                    {item.text}
                  </span>
                  <button
                    onClick={() => delTask.mutate(item.id)}
                    className="opacity-0 transition group-hover:opacity-100"
                  >
                    <Trash2 size={14} className="text-slate-400 hover:text-rose-500" />
                  </button>
                </li>
              ))}
              {checklist.data?.length === 0 && (
                <li className="text-xs text-slate-400">No action items yet.</li>
              )}
            </ul>
          </Section>

          {/* Timeline */}
          <Section title="Application timeline">
            <ol className="relative ml-2 border-l border-slate-200 pl-4 text-sm">
              {job.email_date && (
                <li className="mb-3">
                  <span className="absolute -left-[5px] mt-1.5 h-2.5 w-2.5 rounded-full bg-indigo-500" />
                  <div className="font-medium text-slate-700">Discovered</div>
                  <div className="text-xs text-slate-400">{timeAgo(job.email_date)}</div>
                </li>
              )}
              <li>
                <span className="absolute -left-[5px] mt-1.5 h-2.5 w-2.5 rounded-full bg-emerald-500" />
                <div className="font-medium text-slate-700">
                  Status: {job.status}
                </div>
                <div className="text-xs text-slate-400">
                  {timeAgo(job.status_updated_at)}
                </div>
              </li>
            </ol>
          </Section>

          {/* Ignore */}
          <div className="px-5 py-5">
            <button
              onClick={() => ignore.mutate()}
              className="flex items-center gap-2 text-sm font-medium text-slate-500 hover:text-rose-600"
            >
              <EyeOff size={15} /> Skip this job (hide from board)
            </button>
          </div>
        </div>
      </motion.aside>
    </div>
  );
}
