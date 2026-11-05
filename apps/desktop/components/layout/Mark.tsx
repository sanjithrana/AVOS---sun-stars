/** The AVOS mark: five points, one of them lit. */
export function Mark({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 28 28" className={className} aria-hidden fill="currentColor">
      <circle cx="14" cy="4.5" r="2.3" opacity="0.55" />
      <circle cx="5" cy="12" r="2.3" opacity="0.55" />
      <circle cx="14" cy="14" r="2.8" style={{ fill: "var(--signal)" }} />
      <circle cx="23" cy="12" r="2.3" opacity="0.55" />
      <circle cx="14" cy="23.5" r="2.3" opacity="0.55" />
    </svg>
  );
}
