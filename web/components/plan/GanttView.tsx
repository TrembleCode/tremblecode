"use client";

import type { Milestone, Task } from "@/lib/types";

const BAR_COLOR: Record<string, string> = {
  PENDING: "bg-tui-dim/50",
  ASSIGNED: "bg-tui-dim",
  IN_PROGRESS: "bg-tui-active/70",
  IN_REVIEW: "bg-tui-accent/70",
  APPROVED: "bg-tui-active/50",
  CHANGES_REQUESTED: "bg-tui-danger/60",
  MERGING: "bg-tui-accent",
  DONE: "bg-tui-active",
  BLOCKED: "bg-tui-danger",
};

/**
 * Dependency-ordered CSS gantt: start(task) = max(start(dep) + est(dep)),
 * bar width proportional to estimate_h.
 */
export function GanttView({
  tasks,
  milestones,
}: {
  tasks: Task[];
  milestones: Milestone[];
}) {
  if (tasks.length === 0) {
    return (
      <div className="border border-tui-border bg-tui-panel p-8 text-center text-tui-dim text-xs tracking-widest font-mono">
        NO TASKS TO SCHEDULE
      </div>
    );
  }

  const byKey = new Map(tasks.map((t) => [t.task_key, t]));
  const start = new Map<string, number>();

  function est(t: Task) {
    return t.estimate_h && t.estimate_h > 0 ? t.estimate_h : 1;
  }

  function calcStart(t: Task, seen: Set<string>): number {
    const cached = start.get(t.id);
    if (cached !== undefined) return cached;
    if (seen.has(t.id)) return 0; // cycle guard
    seen.add(t.id);
    let s = 0;
    for (const depKey of t.dependencies ?? []) {
      const dep = byKey.get(depKey);
      if (dep) s = Math.max(s, calcStart(dep, seen) + est(dep));
    }
    start.set(t.id, s);
    return s;
  }

  tasks.forEach((t) => calcStart(t, new Set()));
  const total = Math.max(...tasks.map((t) => (start.get(t.id) ?? 0) + est(t)), 1);

  const sortedMs = [...milestones].sort((a, b) => a.sort - b.sort);
  const groups: { label: string; items: Task[] }[] = sortedMs.map((m) => ({
    label: `${m.key} · ${m.name}`,
    items: tasks.filter((t) => t.milestone_id === m.id),
  }));
  const orphans = tasks.filter(
    (t) => !t.milestone_id || !sortedMs.some((m) => m.id === t.milestone_id)
  );
  if (orphans.length > 0) groups.push({ label: "UNASSIGNED", items: orphans });

  return (
    <div className="border border-tui-border bg-tui-panel p-4 space-y-4">
      <div className="flex items-center gap-4 text-xs text-tui-dim font-mono tracking-widest">
        <span>── TIMELINE (EST. HOURS, DEPENDENCY-ORDERED) ──</span>
        <span className="ml-auto">TOTAL CRITICAL PATH ≈ {total}H</span>
      </div>
      {groups
        .filter((g) => g.items.length > 0)
        .map((g) => (
          <div key={g.label}>
            <div className="text-xs text-tui-accent tracking-widest font-mono uppercase mb-2">
              ▙ {g.label}
            </div>
            <div className="space-y-1">
              {[...g.items]
                .sort(
                  (a, b) => (start.get(a.id) ?? 0) - (start.get(b.id) ?? 0)
                )
                .map((t) => {
                  const s = start.get(t.id) ?? 0;
                  const w = est(t);
                  return (
                    <div key={t.id} className="flex items-center gap-2 group">
                      <div className="w-56 shrink-0 truncate text-xs font-mono">
                        <span className="text-tui-accent">{t.task_key}</span>{" "}
                        <span className="text-tui-dim group-hover:text-tui-text transition-colors">
                          {t.title}
                        </span>
                      </div>
                      <div className="flex-1 relative h-4 bg-tui-bg border border-tui-border/40">
                        <div
                          className={`absolute top-0 bottom-0 ${
                            BAR_COLOR[t.status] ?? "bg-tui-dim"
                          }`}
                          style={{
                            left: `${(s / total) * 100}%`,
                            width: `${Math.max((w / total) * 100, 1)}%`,
                          }}
                          title={`${t.task_key} · ${t.status} · ${w}h${
                            t.dependencies?.length
                              ? ` · after ${t.dependencies.join(", ")}`
                              : ""
                          }`}
                        />
                      </div>
                      <div className="w-12 shrink-0 text-right text-xs text-tui-dim font-mono">
                        {t.estimate_h != null ? `${t.estimate_h}h` : "—"}
                      </div>
                    </div>
                  );
                })}
            </div>
          </div>
        ))}
      <div className="flex flex-wrap gap-3 pt-2 border-t border-tui-border/40 text-xs font-mono text-tui-dim tracking-widest">
        {Object.entries(BAR_COLOR).map(([k, c]) => (
          <span key={k} className="inline-flex items-center gap-1">
            <span className={`inline-block w-3 h-2 ${c}`} />
            {k.replace(/_/g, ".")}
          </span>
        ))}
      </div>
    </div>
  );
}
