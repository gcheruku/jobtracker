import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/**
 * The actual markdown renderer, isolated in its own module so the heavy
 * react-markdown + remark-gfm libraries land in a lazily-loaded chunk (see
 * Markdown.tsx) instead of the initial bundle. Rendered inside the existing
 * `prose` wrapper the callers provide.
 */
export default function MarkdownBody({ children }: { children: string }) {
  return <ReactMarkdown remarkPlugins={[remarkGfm]}>{children}</ReactMarkdown>;
}
