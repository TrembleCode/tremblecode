"use client";

import { useMemo, useState } from "react";
import type { Milestone, ProjectAgent, Task } from "@/lib/types";
import { StatusBadge } from "@/components/StatusBadge";
import { Markdown } from "@/components/Markdown";

const COLUMNS: { label: string; statuses: string[] }[] = [
  { label: "PENDING", statuses: ["PENDING"] },
  { label: "ASSIGNED", statuses: ["ASSIGNED"] },
  { label: "IN PROGRESS", statuses: ["IN_PROGRESS"] },
  {
    label: "REVIEW/MERGE",
    statuses: ["IN_REVIEW", "APPROVED", "CHANGES_REQUESTED", "MERGING"],
  },
  { label: "DONE", statuses: ["DONE"] },
  { label: "BLOCKED", statuses: ["BLOCKED"] },
];

export function TasksBoard({
  tasks,
  milestones,
  agents,
}: {
  tasks: Task[];
  milestones: Milestone[];
  agents: ProjectAgent[];
}) {
  const [agentFilter, setAgentFilter] = useState("");
  const [milestoneFilter, setMilestoneFilter] = useState("");
  const [selected, setSelected] = useState<Task | null>(null);

  const agentById = useMemo(
    () => new Map(agents.map((a) => [a.id, a])),
    [agents]
  );

  const filtered = useMemo(() => {
    let list = tasks;
    if (agentFilter) list = list.filter((t) => t.assignee_agent_id === agentFilter);
    if (milestoneFilter)
      list = list.filter((t) => t.milestone_id === milestoneFilter);
    return list;
  }, [tasks, agentFilter, milestoneFilter]);

  if (tasks.length === 0) {
    return (
      <div className="border border-tui-border bg-tui-panel p-8 text-center text-tui-dim text-xs tracking-widest font-mono">
        NO TASKS IN THIS PLAN
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3 text-xs font-mono">
        <span className="text-tui-dim tracking-widest">── FILTER ──</span>
        <select
          value={agentFilter}
          onChange={(e) => setAgentFilter(e.target.value)}
          className="tui-input !w-auto"
        >
          <option value="">ALL AGENTS</option>
          {agents.map((a) => (
            <option key={a.id} value={a.id}>
              {a.name.toUpperCase()}
            </option>
          ))}
        </select>
        <select
          value={milestoneFilter}
          onChange={(e) => setMilestoneFilter(e.target.value)}
          className="tui-input !w-auto"
        >
          <option value="">ALL MILESTONES</option>
          {milestones
            .slice()
            .sort((a, b) => a.sort - b.sort)
            .map((m) => (
              <option key={m.id} value={m.id}>
                {m.key} · {m.name.toUpperCase()}
              </option>
            ))}
        </select>
        {(agentFilter || milestoneFilter) && (
          <button
            onClick={() => {
              setAgentFilter("");
              setMilestoneFilter("");
            }}
            className="text-tui-dim hover:text-tui-text tracking-widest uppercase"
          >
            [CLEAR]
          </button>
        )}
        <span className="ml-auto text-tui-dim tracking-widest">
          {filtered.length} TASK{filtered.length === 1 ? "" : "S"}
        </span>
      </div>

      {/* Kanban columns */}
      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3 items-start">
        {COLUMNS.map((col) => {
          const colTasks = filtered.filter((t) =>
            col.statuses.includes(t.status)
          );
          return (
            <div key={col.label} className="border border-tui-border bg-tui-panel">
              <div className="px-3 py-2 border-b border-tui-border flex items-center justify-between">
                <span className="text-xs text-tui-dim tracking-widest font-mono uppercase">
                  {col.label}
                </span>
                <span className="text-xs text-tui-border font-mono">
                  [{colTasks.length}]
                </span>
              </div>
              <div className="p-2 space-y-2 min-h-16">
                {colTasks.length === 0 ? (
                  <div className="text-xs text-tui-border font-mono tracking-widest text-center py-3">
                    — EMPTY —
                  </div>
                ) : (
                  colTasks.map((t) => {
                    const assignee = t.assignee_agent_id
                      ? agentById.get(t.assignee_agent_id)
                      : undefined;
                    return (
                      <button
                        key={t.id}
                        onClick={() => setSelected(t)}
                        className="block w-full text-left border border-tui-border bg-tui-bg p-2
                                   hover:border-tui-text/50 transition-colors"
                      >
                        <div className="text-xs text-tui-accent font-mono">
                          {t.task_key}
                        </div>
                        <div className="text-sm text-tui-text font-mono leading-snug mt-0.5">
                          {t.title}
                        </div>
                        <div className="mt-1.5 text-xs text-tui-dim font-mono truncate">
                          {t.role_key}
                          {assignee ? ` · @${assignee.name}` : ""}
                        </div>
                        {t.branch && (
                          <div className="text-xs text-tui-dim font-mono truncate">
                            ⎇ {t.branch}
                          </div>
                        )}
                        <div className="mt-1.5">
                          <StatusBadge status={t.status} />
                        </div>
                      </button>
                    );
                  })
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Side drawer */}
      {selected && (
        <div
          className="fixed inset-0 z-50 flex justify-end bg-tui-bg/70 backdrop-blur-sm"
          onClick={() => setSelected(null)}
        >
          <div
            className="w-full max-w-xl h-full border-l border-tui-border bg-tui-panel overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-4 py-3 border-b border-tui-border sticky top-0 bg-tui-panel">
              <div>
                <div className="text-xs text-tui-accent font-mono tracking-widest">
                  {selected.task_key}
                </div>
                <div className="font-display text-2xl text-tui-text tracking-widest uppercase">
                  {selected.title}
                </div>
              </div>
              <button
                onClick={() => setSelected(null)}
                className="border border-tui-border px-3 py-1 text-xs text-tui-dim font-mono
                           hover:text-tui-text tracking-widest uppercase"
              >
                // CLOSE
              </button>
            </div>
            <div className="p-4 space-y-4">
              <div className="flex flex-wrap items-center gap-2 text-xs font-mono text-tui-dim tracking-widest">
                <StatusBadge status={selected.status} />
                <span>ROLE: {selected.role_key}</span>
                {selected.assignee_agent_id && (
                  <span className="text-tui-text">
                    @{agentById.get(selected.assignee_agent_id)?.name ?? "?"}
                  </span>
                )}
                {selected.estimate_h != null && (
                  <span>EST: {selected.estimate_h}H</span>
                )}
                {selected.branch && <span>⎇ {selected.branch}</span>}
              </div>

              {selected.blocked_reason && (
                <div className="border border-tui-danger/40 bg-tui-danger/5 p-3">
                  <div className="text-xs text-tui-danger tracking-widest font-mono uppercase mb-1">
                    ⚠ BLOCKED
                  </div>
                  <div className="text-sm text-tui-text font-mono">
                    {selected.blocked_reason}
                  </div>
                </div>
              )}

              {(selected.dependencies ?? []).length > 0 && (
                <div>
                  <div className="text-xs text-tui-dim tracking-widest font-mono uppercase mb-1">
                    ── DEPENDENCIES ──
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {selected.dependencies.map((d) => (
                      <span
                        key={d}
                        className="border border-tui-border px-2 py-0.5 text-xs text-tui-accent font-mono"
                      >
                        {d}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              <div>
                <div className="text-xs text-tui-dim tracking-widest font-mono uppercase mb-2">
                  ── BRIEFING ──
                </div>
                <Markdown content={selected.description_md} />
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
