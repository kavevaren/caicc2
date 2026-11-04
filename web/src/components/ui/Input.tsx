import type { InputHTMLAttributes } from "react";

type Props = InputHTMLAttributes<HTMLInputElement> & {
  label?: string;
  error?: string | null;
};

export function Input({ label, error, id, className = "", ...rest }: Props) {
  return (
    <label className="field" htmlFor={id}>
      {label && <span className="field-label">{label}</span>}
      <input id={id} className={`field-input ${className}`.trim()} {...rest} />
      {error && (
        <span className="field-error" role="alert">
          {error}
        </span>
      )}
    </label>
  );
}
