import type { ButtonHTMLAttributes, ReactNode } from "react";

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger" | "black";
  icon?: ReactNode;
  children?: ReactNode;
};

/** DESIGN §1.2: min 44 px tall, radius 10, focus outline from tokens. */
export function Button({ variant = "secondary", icon, children, className = "", type = "button", ...rest }: Props) {
  const cls = [`btn`, variant !== "secondary" ? variant : "", className].filter(Boolean).join(" ");
  return (
    <button type={type} className={cls} {...rest}>
      {icon}
      {children !== undefined && <>{children}</>}
    </button>
  );
}
