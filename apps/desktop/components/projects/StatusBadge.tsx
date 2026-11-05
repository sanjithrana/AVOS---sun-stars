import { statusStyle } from "./status";

export function StatusBadge({ status, className = "" }: { status: string; className?: string }) {
  const s = statusStyle(status);
  const Icon = s.icon;
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium ${s.bg} ${s.text} ${s.border} ${className}`}
    >
      <Icon className={`h-3 w-3 ${s.active ? "animate-pulse" : ""}`} />
      {s.label}
    </span>
  );
}
