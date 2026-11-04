import type { ReactNode, SelectHTMLAttributes } from "react";

type Props = SelectHTMLAttributes<HTMLSelectElement> & {
  label?: string;
  error?: string | null;
  children: ReactNode;
};

export function Select({ label, error, id, children, className = "", ...rest }: Props) {
  return (
    <label className="field" htmlFor={id}>
      {label && <span className="field-label">{label}</span>}
      <select id={id} className={`field-input ${className}`.trim()} {...rest}>
        {children}
      </select>
      {error && (
        <span className="field-error" role="alert">
          {error}
        </span>
      )}
    </label>
  );
}
