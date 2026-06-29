import { lazy, Suspense } from "react";

// Load the markdown renderer (and its remark-gfm dependency) on demand. It's
// only needed when a job description / compare report is shown, so keeping it
// out of the initial bundle trims the critical-path JS.
const MarkdownBody = lazy(() => import("./MarkdownBody"));

export function Markdown({ children }: { children: string }) {
  return (
    <Suspense fallback={<p className="text-sm text-slate-400">Loading…</p>}>
      <MarkdownBody>{children}</MarkdownBody>
    </Suspense>
  );
}
