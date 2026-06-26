import { AnimatePresence } from "framer-motion";
import { JobDrawer } from "./JobDrawer";
import type { Job } from "../lib/types";

/**
 * Hosts the slide-over drawer (and its AnimatePresence) behind a single lazy
 * boundary so framer-motion stays out of the initial bundle. App mounts this
 * on the first drawer open and keeps it mounted thereafter, so the exit
 * animation still plays when `job` goes back to null.
 */
export default function DrawerHost({
  job,
  onClose,
  onChanged,
}: {
  job: Job | null;
  onClose: () => void;
  onChanged: () => void;
}) {
  return (
    <AnimatePresence>
      {job && (
        <JobDrawer key={job.job_key} job={job} onClose={onClose} onChanged={onChanged} />
      )}
    </AnimatePresence>
  );
}
