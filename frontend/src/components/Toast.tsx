import { createPortal } from "react-dom";

/**
 * A single transient notification. Slides up from the bottom on mobile and
 * sits in the bottom-right on desktop. Rendered via a portal so it's never
 * trapped by an ancestor's backdrop-filter/overflow.
 *
 * Uses a CSS transition (not framer-motion) so the toast — which mounts on
 * first paint via the Fetch button — doesn't pull the animation library onto
 * the critical path. It stays mounted and just animates opacity/translate, so
 * both enter and exit transitions still play.
 */
export function Toast({ open, children }: { open: boolean; children: React.ReactNode }) {
  return createPortal(
    <div
      className={`fixed inset-x-3 bottom-4 z-[60] transform-gpu transition-all duration-300 ease-out sm:inset-x-auto sm:right-4 sm:w-96 ${
        open ? "translate-y-0 opacity-100" : "pointer-events-none translate-y-10 opacity-0"
      }`}
    >
      {children}
    </div>,
    document.body
  );
}
