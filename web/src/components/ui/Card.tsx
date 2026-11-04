import type { ReactNode } from "react";

type Props = {
  title?: ReactNode;
  more?: { label: string; to?: string; onClick?: () => void };
  children: ReactNode;
  className?: string;
  id?: string;
};

/** DESIGN §4: content lives in cards (radius 16, padding 24, border --border). */
export function Card({ title, more, children, className = "", id }: Props) {
  return (
    <section className={`card ${className}`.trim()}>
      {title !== undefined && (
        <h2 id={id}>
          {title}
          {more && (
            more.to ? (
              <a className="more" href={`#${more.to}`}>
                {more.label}
              </a>
            ) : (
              <button type="button" className="more" onClick={more.onClick}>
                {more.label}
              </button>
            )
          )}
        </h2>
      )}
      {children}
    </section>
  );
}
