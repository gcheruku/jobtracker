import { createPortal } from "react-dom";
import { AnimatePresence, motion } from "framer-motion";

/**
 * A single transient notification. Slides up from the bottom on mobile and
 * sits in the bottom-right on desktop. Rendered via a portal so it's never
 * trapped by an ancestor's backdrop-filter/overflow.
 */
export function Toast({ open, children }: { open: boolean; children: React.ReactNode }) {
  return createPortal(
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0, y: 40 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 40 }}
          transition={{ type: "spring", damping: 26, stiffness: 320 }}
          className="fixed inset-x-3 bottom-4 z-[60] sm:inset-x-auto sm:right-4 sm:w-96"
        >
          {children}
        </motion.div>
      )}
    </AnimatePresence>,
    document.body
  );
}
