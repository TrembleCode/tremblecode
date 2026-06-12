const STATUS_MAP: Record<string, { label: string; className: string }> = {
  DISCUSSION:  { label: "[DISCUSSION]",  className: "text-tui-accent border-tui-accent/40" },
  DRAFT:       { label: "[DRAFT]",       className: "text-tui-dim border-tui-border" },
  PLANNING:    { label: "[PLANNING]",    className: "text-tui-accent border-tui-accent/40 animate-flicker" },
  PLAN_REVIEW: { label: "[PLAN.REVIEW]", className: "text-tui-accent border-tui-accent/60 animate-flicker" },
  EXECUTING:   { label: "[EXECUTING]",   className: "text-tui-active border-tui-active/60" },
  PAUSED:      { label: "[PAUSED]",      className: "text-tui-dim border-tui-border" },
  COMPLETED:   { label: "[COMPLETED]",   className: "text-tui-active border-tui-active/40" },
  FAILED:      { label: "[FAILED]",      className: "text-tui-danger border-tui-danger/60" },
  // task statuses
  PENDING:           { label: "[PENDING]",     className: "text-tui-dim border-tui-border" },
  ASSIGNED:          { label: "[ASSIGNED]",    className: "text-tui-text border-tui-border" },
  IN_PROGRESS:       { label: "[IN.PROGRESS]", className: "text-tui-active border-tui-active/40" },
  IN_REVIEW:         { label: "[IN.REVIEW]",   className: "text-tui-accent border-tui-accent/40" },
  APPROVED:          { label: "[APPROVED]",    className: "text-tui-active border-tui-active/60" },
  CHANGES_REQUESTED: { label: "[CHANGES.REQ]", className: "text-tui-danger border-tui-danger/40" },
  MERGING:           { label: "[MERGING]",     className: "text-tui-accent border-tui-accent/60 animate-flicker" },
  DONE:              { label: "[DONE]",        className: "text-tui-active border-tui-active/40" },
  BLOCKED:           { label: "[BLOCKED]",     className: "text-tui-danger border-tui-danger/60 animate-flicker" },
};

export function StatusBadge({ status }: { status: string }) {
  const entry = STATUS_MAP[status] ?? {
    label: `[${status.replace(/_/g, ".")}]`,
    className: "text-tui-dim border-tui-border",
  };
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 text-xs font-mono border tracking-widest ${entry.className}`}
    >
      {entry.label}
    </span>
  );
}
