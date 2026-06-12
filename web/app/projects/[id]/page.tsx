"use client";

import { use, useState } from "react";
import { useRouter } from "next/navigation";
import useSWR from "swr";
import { api, fetcher } from "@/lib/api";
import type {
  CostSummary,
  Message,
  Plan,
  ProjectAgent,
  ProjectDetail,
} from "@/lib/types";
import { StatusBadge } from "@/components/StatusBadge";
import { ProjectNav } from "@/components/ProjectNav";
import { AddAgentButton } from "@/components/AddAgentButton";
import { NetCanvas } from "@/components/comms/NetCanvas";
import { useAfEvents } from "@/components/WebSocketProvider";

const MILESTONE_STYLE: Record<string, string> = {
  pending: "text-tui-dim border-tui-border",
  active: "text-tui-accent border-tui-accent/40 animate-flicker",
  gate_open: "text-tui-danger border-tui-danger/60 animate-flicker",
  approved: "text-tui-active border-tui-active/60",
};

const RUNNING = ["PLANNING", "PLAN_REVIEW", "EXECUTING"];

export default function ProjectPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const router = useRouter();
  const { data: project, mutate } = useSWR<ProjectDetail>(
    `/api/projects/${id}`,
    fetcher
  );
  const { data: liveAgents, mutate: mutateAgents } = useSWR<ProjectAgent[]>(
    `/api/projects/${id}/agents`,
    fetcher
  );
  const { data: messages } = useSWR<Message[]>(
    `/api/projects/${id}/messages`,
    fetcher,
    { refreshInterval: 3000 }
  );
  const { data: costs } = useSWR<CostSummary>(
    `/api/projects/${id}/costs`,
    fetcher,
    { shouldRetryOnError: false }
  );
  const { data: plan } = useSWR<Plan>(`/api/projects/${id}/plan`, fetcher, {
    shouldRetryOnError: false,
  });

  // Live agent LEDs: refresh agent data whenever an agent state event lands.
  useAfEvents((ev) => {
    if (ev.event.startsWith("agent.")) {
      mutateAgents();
      mutate();
    }
  }, id);

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!project) {
    return (
      <div className="text-tui-dim font-mono text-sm tracking-widest animate-flicker">
        LOADING PROJECT DATA...
      </div>
    );
  }

  const agents = liveAgents ?? project.agents;
  const liveCount = agents.filter((a) => a.state === "busy").length;

  async function lifecycle(action: "start" | "pause" | "resume") {
    setBusy(true);
    setError(null);
    try {
      await api.post(`/api/projects/${id}/${action}`);
      mutate();
      mutateAgents();
    } catch (e) {
      setError(e instanceof Error ? e.message : `${action} failed`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="font-display text-4xl text-tui-active tracking-widest uppercase">
            {project.name}
          </h1>
          <div className="mt-1 text-xs text-tui-dim tracking-widest font-mono">
            {project.slug} {project.host_dir ? `· ${project.host_dir}` : ""}
          </div>
        </div>
        <div className="flex items-center gap-3">
          {/* Lifecycle controls */}
          {project.status === "DRAFT" && (
            <button
              onClick={() => lifecycle("start")}
              disabled={busy}
              className="border border-tui-active/60 text-tui-active px-4 py-2 text-xs font-mono
                         hover:bg-tui-active/10 disabled:opacity-30 tracking-widest uppercase"
            >
              {busy ? "..." : "// START"}
            </button>
          )}
          {project.status === "PAUSED" && (
            <button
              onClick={() => lifecycle("resume")}
              disabled={busy}
              className="border border-tui-active/60 text-tui-active px-4 py-2 text-xs font-mono
                         hover:bg-tui-active/10 disabled:opacity-30 tracking-widest uppercase"
            >
              {busy ? "..." : "// RESUME"}
            </button>
          )}
          {RUNNING.includes(project.status) && (
            <button
              onClick={() => lifecycle("pause")}
              disabled={busy}
              className="border border-tui-accent/60 text-tui-accent px-4 py-2 text-xs font-mono
                         hover:bg-tui-accent/10 disabled:opacity-30 tracking-widest uppercase"
            >
              {busy ? "..." : "// PAUSE"}
            </button>
          )}
          <StatusBadge status={project.status} />
        </div>
      </div>

      {error && (
        <div className="text-xs text-tui-danger font-mono tracking-widest">
          ERR: {error}
        </div>
      )}

      <ProjectNav projectId={id} />

      {/* Cost strip */}
      {costs && (
        <div className="border border-tui-border bg-tui-panel px-4 py-2 flex flex-wrap items-center gap-6 text-xs font-mono tracking-widest">
          <span className="text-tui-dim">── BURN ──</span>
          <span className="text-tui-accent">
            ${costs.total_usd.toFixed(2)}{" "}
            <span className="text-tui-dim">TOTAL</span>
          </span>
          <span className="text-tui-text">
            {fmtTokens(costs.total_tokens)}{" "}
            <span className="text-tui-dim">TOKENS</span>
          </span>
          {costs.by_day.length > 0 && (
            <span className="text-tui-dim">
              TODAY: $
              {(costs.by_day[costs.by_day.length - 1]?.cost_usd ?? 0).toFixed(2)}
            </span>
          )}
        </div>
      )}

      {/* Milestone tracker */}
      {plan && plan.milestones.length > 0 && (
        <div className="border border-tui-border bg-tui-panel px-4 py-2 flex flex-wrap items-center gap-2 text-xs font-mono">
          <span className="text-tui-dim tracking-widest mr-2">
            ── MILESTONES ──
          </span>
          {plan.milestones
            .slice()
            .sort((a, b) => a.sort - b.sort)
            .map((m, i, arr) => (
              <span key={m.id} className="inline-flex items-center gap-2">
                <span
                  className={`border px-2 py-0.5 tracking-widest ${
                    MILESTONE_STYLE[m.status] ?? "text-tui-dim border-tui-border"
                  }`}
                  title={m.description}
                >
                  {m.key} {m.name.toUpperCase()} [
                  {m.status.replace(/_/g, ".").toUpperCase()}]
                </span>
                {i < arr.length - 1 && (
                  <span className="text-tui-border">━▶</span>
                )}
              </span>
            ))}
        </div>
      )}

      {/* Live net scope */}
      <section>
        <div className="flex items-center justify-between mb-2">
          <h2 className="font-display text-xl text-tui-active tracking-widest uppercase">
            // LIVE NET
          </h2>
          {project.host_dir && (
            <AddAgentButton projectId={id} onAdded={() => mutateAgents()} />
          )}
        </div>
        {agents.length === 0 ? (
          <div className="border border-tui-border bg-tui-panel p-4 text-xs text-tui-dim tracking-widest">
            NO AGENTS DEPLOYED — agents are provisioned when the project starts
          </div>
        ) : (
          <div className="relative border border-tui-border bg-tui-panel h-[28rem] overflow-hidden">
            <div className="absolute top-0 left-0 z-10 flex items-center gap-2 px-3 py-1.5 text-[10px] font-mono tracking-widest text-tui-dim">
              <span className="text-tui-active animate-blink">●</span>
              NET SCOPE · CLICK A NODE TO INSPECT
            </div>
            <div className="absolute top-0 right-0 z-10 flex items-center gap-3 px-3 py-1.5 text-[10px] font-mono tracking-widest">
              <span className="text-tui-active">{liveCount} ACTIVE</span>
              <span className="text-tui-dim">{agents.length} NODES</span>
            </div>
            <div className="absolute bottom-0 left-0 z-10 flex items-center gap-3 px-3 py-1.5 text-[10px] font-mono tracking-widest text-tui-dim">
              <LegendDot cls="bg-tui-active" label="WORKING" />
              <LegendDot cls="bg-tui-dim" label="IDLE" />
              <LegendDot cls="bg-tui-danger" label="STOPPED" />
            </div>
            <NetCanvas
              agents={agents}
              messages={messages ?? []}
              onSelectAgent={(name) => {
                if (agents.some((a) => a.name === name))
                  router.push(`/projects/${id}/agents/${name}`);
              }}
            />
          </div>
        )}
      </section>
    </div>
  );
}

function LegendDot({ cls, label }: { cls: string; label: string }) {
  return (
    <span className="flex items-center gap-1.5">
      <span className={`inline-block w-2 h-2 rounded-full ${cls}`} />
      {label}
    </span>
  );
}

function fmtTokens(n: number) {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}
