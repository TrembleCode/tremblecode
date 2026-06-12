"use client";

import { useMemo } from "react";
import useSWR from "swr";
import { fetcher } from "@/lib/api";
import type { Escalation, Project } from "@/lib/types";
import { EscalationCard } from "@/components/EscalationCard";

export default function InboxPage() {
  const { data: escalations, mutate } = useSWR<Escalation[]>(
    "/api/inbox?status=open",
    fetcher
  );
  const { data: projects } = useSWR<Project[]>("/api/projects", fetcher);

  const projectName = useMemo(() => {
    const map = new Map<string, string>();
    (projects ?? []).forEach((p) => map.set(p.id, p.name));
    return map;
  }, [projects]);

  const open = (escalations ?? []).filter((e) => e.status === "open");

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-4xl text-tui-active tracking-widest uppercase">
          Inbox
        </h1>
        <div className="mt-1 text-xs text-tui-dim tracking-widest">
          HOT TOPICS · ESCALATIONS · GATES — ALL PROJECTS
        </div>
      </div>

      {!escalations ? (
        <div className="text-tui-dim font-mono text-sm tracking-widest animate-flicker">
          SCANNING ALL CHANNELS...
        </div>
      ) : open.length === 0 ? (
        <div className="border border-tui-border bg-tui-panel p-8 text-center text-tui-dim">
          <div className="font-display text-2xl tracking-widest">ALL QUIET</div>
          <div className="mt-2 text-xs tracking-widest font-mono">
            no open escalations across the fleet
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          {open.map((e) => (
            <EscalationCard
              key={e.id}
              escalation={e}
              projectName={projectName.get(e.project_id) ?? e.project_id}
              onChanged={() => mutate()}
            />
          ))}
        </div>
      )}
    </div>
  );
}
