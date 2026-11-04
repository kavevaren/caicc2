/** Static brand atom (two ellipses + core) — the sidebar lockup mark. */
export function BrandMark({ size = 34 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 512 512" aria-hidden="true">
      <ellipse cx="256" cy="256" rx="170" ry="70" fill="none" stroke="var(--primary)" strokeWidth="24" transform="rotate(-30 256 256)" />
      <ellipse cx="256" cy="256" rx="170" ry="70" fill="none" stroke="var(--primary)" strokeWidth="24" transform="rotate(30 256 256)" />
      <circle cx="256" cy="256" r="28" fill="var(--accent)" />
    </svg>
  );
}

export function BrandLockup({ size = 34 }: { size?: number }) {
  return (
    <span className="brand">
      <BrandMark size={size} />
      <span>Orvina</span>
    </span>
  );
}
