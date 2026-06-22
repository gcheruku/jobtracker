import { motion } from "framer-motion";
import type { Job } from "../lib/types";
import { JobDetail } from "./JobDetail";

export function JobDrawer({
  job,
  onClose,
  onChanged,
}: {
  job: Job;
  onClose: () => void;
  onChanged: () => void;
}) {
  return (
    <div className="fixed inset-0 z-30 flex justify-end">
      <div className="absolute inset-0 bg-slate-900/30" onClick={onClose} />
      <motion.aside
        initial={{ x: 480 }}
        animate={{ x: 0 }}
        exit={{ x: 480 }}
        transition={{ type: "spring", damping: 28, stiffness: 280 }}
        className="relative w-full max-w-md shadow-2xl"
      >
        <JobDetail job={job} onClose={onClose} onChanged={onChanged} />
      </motion.aside>
    </div>
  );
}
