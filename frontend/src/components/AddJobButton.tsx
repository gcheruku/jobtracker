import { useState } from "react";
import { createPortal } from "react-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Loader2, X, Link2 } from "lucide-react";
import { api } from "../lib/api";
import type { Job } from "../lib/types";

type Phase = "reading" | "scoring";

/**
 * Dashboard action: add a job by pasting a career-portal posting URL. The
 * backend fetches the page, extracts title/company/location/salary + the
 * description, creates the job, and runs the semantic match; we then trigger the
 * LLM compare (best-effort) and open the new job so the user lands on it.
 */
export function AddJobButton({ onAdded }: { onAdded: (job: Job) => void }) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [url, setUrl] = useState("");
  const [phase, setPhase] = useState<Phase>("reading");

  const add = useMutation({
    mutationFn: async (u: string) => {
      setPhase("reading");
      const job = await api.createJobFromUrl(u.trim());
      // The description is now stored, so Compare works. Run it best-effort —
      // a missing key/resume shouldn't fail the add.
      setPhase("scoring");
      try {
        await api.runCompare(job.job_key);
      } catch {
        /* compare is optional; the user can re-run it from the drawer */
      }
      return job;
    },
    onSuccess: (job) => {
      qc.invalidateQueries({ queryKey: ["jobs"] });
      qc.invalidateQueries({ queryKey: ["stats"] });
      qc.invalidateQueries({ queryKey: ["activity"] });
      setUrl("");
      setOpen(false);
      onAdded(job);
    },
  });

  const close = () => {
    if (add.isPending) return; // don't abandon an in-flight add
    setOpen(false);
    add.reset();
  };

  const submit = () => {
    if (url.trim()) add.mutate(url);
  };

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        title="Add a job from its posting URL"
        className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 shadow-sm transition hover:bg-slate-50"
      >
        <Plus size={15} />
        <span className="hidden sm:inline">Add job</span>
      </button>

      {open &&
        createPortal(
          <div className="fixed inset-0 z-50 grid place-items-center p-4">
            <div className="absolute inset-0 bg-slate-900/40" onClick={close} />
            <div className="relative w-full max-w-lg rounded-xl bg-white p-5 shadow-2xl">
              <div className="mb-1 flex items-center justify-between">
                <h3 className="text-base font-semibold text-slate-800">Add a job from a link</h3>
                <button
                  onClick={close}
                  disabled={add.isPending}
                  className="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700 disabled:opacity-40"
                  title="Close"
                >
                  <X size={18} />
                </button>
              </div>
              <p className="mb-3 text-sm text-slate-500">
                Paste a posting URL from a company career portal. We’ll read the title,
                company, location, salary, and description, then score it against your resume.
              </p>

              <div className="relative">
                <Link2
                  size={16}
                  className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
                />
                <input
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && !add.isPending && submit()}
                  autoFocus
                  placeholder="https://careers.company.com/jobs/12345"
                  className="w-full rounded-lg border border-slate-200 py-2 pl-9 pr-3 text-sm outline-none focus:border-indigo-400"
                />
              </div>

              {add.isError && (
                <p className="mt-2 text-sm text-rose-600">
                  {add.error instanceof Error ? add.error.message : "Couldn’t add that link."}
                </p>
              )}

              <div className="mt-4 flex items-center justify-end gap-2">
                <button
                  onClick={close}
                  disabled={add.isPending}
                  className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-40"
                >
                  Cancel
                </button>
                <button
                  onClick={submit}
                  disabled={!url.trim() || add.isPending}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-indigo-700 disabled:opacity-60"
                >
                  {add.isPending && <Loader2 size={15} className="animate-spin" />}
                  {add.isPending
                    ? phase === "reading"
                      ? "Reading the posting…"
                      : "Scoring…"
                    : "Add job"}
                </button>
              </div>
            </div>
          </div>,
          document.body
        )}
    </>
  );
}
