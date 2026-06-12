"use client";

import { use, useState } from "react";
import useSWR from "swr";
import { api, fetcher } from "@/lib/api";
import type { CostSummary, Plan, ProjectAgent } from "@/lib/types";
import { ProjectHeader } from "@/components/ProjectHeader";
import { AgentTerminal } from "@/components/AgentTerminal";

const STATE_COLOR: Record<string, string> = {
  idle: "text-tui-active",
  busy: "text-tui-accent",
  waiting_human: "text-tui-danger",
  provisioning: "text-tui-dim",
  starting: "text-tui-dim",
  stopped: "text-tui-dim",
  error: "text-tui-danger",
};

export default function AgentPage({
  params,
}: {
  params: Promise<{ id: string; name: string }>;
}) {
  const { id, name } = use(params);
  const { data: agents, mutate } = useSWR<ProjectAgent[]>(
    `/api/projects/${id}/agents`,
    fetcher
  );
  const { data: costs } = useSWR<CostSummary>(
    `/api/projects/${id}/costs`,
    fetcher,
    { shouldRetryOnError: false }
  );
  const { data: plan } = useSWR<Plan>(`/api/projects/${id}/plan`, fetcher, {
    shouldRetryOnError: false,
  });

  const [mode, setMode] = useState<"ro" | "rw">("ro");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const agent = (agents ?? []).find((a) => a.name === name);
  const agentCost = costs?.by_agent.find((c) => c.agent === name);
  const currentTask = agent?.current_task_id
    ? plan?.tasks.find((t) => t.id === agent.current_task_id)
    : undefined;

  async function action(path: string, label: string) {
    if (!agent) return;
    setBusy(true);
    setError(null);
    try {
      await api.post(`/api/agents/${agent.id}/${path}`);
      mutate();
    } catch (e) {
      setError(e instanceof Error ? e.message : `${label} failed`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col h-full space-y-4">
      <ProjectHeader projectId={id} section={`AGENT · ${name.toUpperCase()}`} />

      {!agents ? (
        <div className="text-tui-dim font-mono text-sm tracking-widest animate-flicker">
          LOCATING AGENT...
        </div>
      ) : !agent ? (
        <div className="border border-tui-danger/40 bg-tui-panel p-8 text-center text-tui-danger">
          <div className="font-display text-2xl tracking-widest">
            AGENT NOT FOUND
          </div>
          <div className="mt-2 text-xs tracking-widest font-mono">
            no agent named &quot;{name}&quot; in this project
          </div>
        </div>
      ) : (
        <div className="flex-1 min-h-0 flex gap-4">
          {/* Terminal */}
          <div className="flex-1 min-w-0 flex flex-col border border-tui-border bg-tui-panel">
            <div className="flex items-center gap-3 px-3 py-2 border-b border-tui-border">
              <span className="text-xs text-tui-dim font-mono tracking-widest uppercase">
                ── TTY {agent.name} ──
              </span>
              <div className="ml-auto flex items-center gap-2">
                {mode === "rw" && (
                  <span className="text-xs text-tui-danger font-mono tracking-widest animate-blink">
                    ⚠ LIVE INPUT
                  </span>
                )}
                <button
                  onClick={() => setMode("ro")}
                  className={`px-3 py-1 text-xs font-mono tracking-widest border ${
                    mode === "ro"
                      ? "border-tui-active/60 text-tui-active bg-tui-active/10"
                      : "border-tui-border text-tui-dim hover:text-tui-text"
                  }`}
                >
                  RO
                </button>
                <button
                  onClick={() => setMode("rw")}
                  className={`px-3 py-1 text-xs font-mono tracking-widest border ${
                    mode === "rw"
                      ? "border-tui-danger/60 text-tui-danger bg-tui-danger/10"
                      : "border-tui-border text-tui-dim hover:text-tui-danger"
                  }`}
                >
                  RW
                </button>
              </div>
            </div>
            <div className="flex-1 min-h-0 p-1">
              <AgentTerminal key={mode} agentId={agent.id} mode={mode} />
            </div>
          </div>

          {/* Side panel */}
          <aside className="w-72 shrink-0 space-y-3">
            <div className="border border-tui-border bg-tui-panel p-4 space-y-3">
              <div className="flex items-center justify-between">
                <span className="font-display text-xl text-tui-text tracking-widest uppercase">
                  {agent.name}
                </span>
                <span
                  className={`text-xs font-mono ${STATE_COLOR[agent.state] ?? "text-tui-dim"}`}
                >
                  <span className="animate-blink">●</span>{" "}
                  {agent.state.toUpperCase()}
                </span>
              </div>
              <Row label="ROLE" value={agent.role_key} />
              <Row label="KIND" value={agent.kind} />
              <Row label="MODEL" value={agent.model} />
              <Row
                label="TASK"
                value={
                  currentTask
                    ? `${currentTask.task_key} · ${currentTask.title}`
                    : agent.current_task_id ?? "—"
                }
              />
              <Row
                label="LAST ACTIVITY"
                value={
                  agent.last_activity_at
                    ? new Date(agent.last_activity_at).toLocaleString()
                    : "—"
                }
              />
            </div>

            <div className="border border-tui-border bg-tui-panel p-4 space-y-2">
              <div className="text-xs text-tui-dim tracking-widest font-mono uppercase">
                ── SPEND ──
              </div>
              {agentCost ? (
                <>
                  <Row
                    label="COST"
                    value={`$${agentCost.cost_usd.toFixed(4)}`}
                    accent
                  />
                  <Row
                    label="IN / OUT"
                    value={`${fmtTok(agentCost.input_tokens)} / ${fmtTok(agentCost.output_tokens)}`}
                  />
                  <Row
                    label="CACHE R/W"
                    value={`${fmtTok(agentCost.cache_read_tokens)} / ${fmtTok(agentCost.cache_write_tokens)}`}
                  />
                </>
              ) : (
                <div className="text-xs text-tui-border font-mono tracking-widest">
                  NO SPEND RECORDED
                </div>
              )}
            </div>

            <div className="border border-tui-border bg-tui-panel p-4 space-y-2">
              <div className="text-xs text-tui-dim tracking-widest font-mono uppercase">
                ── CONTROL ──
              </div>
              {error && (
                <div className="text-xs text-tui-danger font-mono tracking-widest">
                  ERR: {error}
                </div>
              )}
              <button
                onClick={() => action("interrupt", "interrupt")}
                disabled={busy}
                className="w-full border border-tui-accent/60 text-tui-accent px-3 py-2 text-xs font-mono
                           hover:bg-tui-accent/10 disabled:opacity-30 tracking-widest uppercase"
              >
                // INTERRUPT
              </button>
              <button
                onClick={() => action("restart", "restart")}
                disabled={busy}
                className="w-full border border-tui-danger/60 text-tui-danger px-3 py-2 text-xs font-mono
                           hover:bg-tui-danger/10 disabled:opacity-30 tracking-widest uppercase"
              >
                // RESTART
              </button>
            </div>
          </aside>
        </div>
      )}
    </div>
  );
}

function Row({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent?: boolean;
}) {
  return (
    <div className="flex justify-between gap-2 text-xs font-mono">
      <span className="text-tui-dim tracking-widest shrink-0">{label}</span>
      <span
        className={`text-right truncate ${accent ? "text-tui-accent" : "text-tui-text"}`}
        title={value}
      >
        {value}
      </span>
    </div>
  );
}

function fmtTok(n: number) {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}
