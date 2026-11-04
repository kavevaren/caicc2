import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.css";

/**
 * remark-math only understands $...$ and $$...$$. Convert \( x \) -> $x$ and
 * \[ x \] -> $$x$$ before parsing, leaving fenced code blocks and `inline
 * code` untouched (code is stashed behind NUL placeholders first).
 */
function mathDelimiters(src: string): string {
  const stash: string[] = [];
  const keep = (s: string) => {
    stash.push(s);
    return `\u0000${stash.length - 1}\u0000`;
  };
  let s = src.replace(/(```[\s\S]*?```|~~~[\s\S]*?~~~)/g, keep);
  s = s.replace(/`[^`\n]*`/g, keep);
  s = s.replace(/\\\[\s?[\s\S]*?\s?\\\]/g, (t) => "$$" + t.slice(2, -2) + "$$");
  s = s.replace(/\\\(.*?\\\)/g, (t) => "$" + t.slice(2, -2) + "$");
  return s.replace(/\u0000(\d+)\u0000/g, (_m, i: string) => stash[Number(i)]);
}

/**
 * Markdown with LaTeX (KaTeX) and GFM. Code stays plain <pre><code> (no
 * highlight, per _LEAN §4). Default export: lazy-loaded by DocumentView so
 * the KaTeX CSS loads only on pages that render Markdown (L3 task 8).
 */
export default function Markdown({ source }: { source: string }) {
  return (
    <div className="md">
      <ReactMarkdown remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[rehypeKatex]}>
        {mathDelimiters(source)}
      </ReactMarkdown>
    </div>
  );
}
