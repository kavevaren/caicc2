import type { ReactNode } from "react";

/** DESIGN §3.7: a small static atom with one hollow electron. */
export function EmptyState({ title, body, action }: { title: string; body?: string; action?: ReactNode }) {
  return (
    <div className="empty">
      <svg className="empty-atom" viewBox="0 0 512 512" aria-hidden="true">
        <ellipse cx="256" cy="256" rx="150" ry="58" fill="none" stroke="var(--orbit)" strokeWidth="16" transform="rotate(-30 256 256)" />
        <circle cx="371" cy="193" r="20" fill="none" stroke="var(--border-strong)" strokeWidth="9" />
        <circle cx="256" cy="256" r="18" fill="var(--accent)" opacity=".55" />
      </svg>
      <p className="empty-title">{title}</p>
      {body && <p className="empty-body">{body}</p>}
      {action}
    </div>
  );
}
