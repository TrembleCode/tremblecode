"use client";

import { use, useState } from "react";
import useSWR from "swr";
import { fetcher } from "@/lib/api";
import type { Escalation } from "@/lib/types";
import { ProjectHeader } from "@/components/ProjectHeader";
import { EscalationCard } from "@/components/EscalationCard";

export default function ProjectInboxPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const { data: escalations, mutate } = useSWR<Escalation[]>(
    `/api/projects/${id}/escalations`,
    fetcher
  );
  const [showResolved, setShowResolved] = useState(false);

  const open = (escalations ?? []).filter((e) => e.status === "open");
  const resolved = (escalations ?? []).filter((e) => e.status !== "open");

  return (
    <div className="space-y-6">
      <ProjectHeader projectId={id} section="HIL · HUMAN-IN-THE-LOOP ESCALATIONS" />

      {!escalations ? (
        <div className="text-tui-dim font-mono text-sm tracking-widest animate-flicker">
          SCANNING FOR ESCALATIONS...
        </div>
      ) : (
        <>
          {open.length === 0 ? (
            <div className="border border-tui-border bg-tui-panel p-8 text-center text-tui-dim">
              <div className="font-display text-2xl tracking-widest">
                ALL QUIET
              </div>
              <div className="mt-2 text-xs tracking-widest font-mono">
                no open escalations for this project
              </div>
            </div>
          ) : (
            <div className="space-y-3">
              {open.map((e) => (
                <EscalationCard
                  key={e.id}
                  escalation={e}
                  onChanged={() => mutate()}
                />
              ))}
            </div>
          )}

          {resolved.length > 0 && (
            <section>
              <button
                onClick={() => setShowResolved(!showResolved)}
                className="text-xs text-tui-dim font-mono tracking-widest hover:text-tui-text uppercase"
              >
                {showResolved ? "▾" : "▸"} ── RESOLVED [{resolved.length}] ──
              </button>
              {showResolved && (
                <div className="mt-3 space-y-3 opacity-70">
                  {resolved.map((e) => (
                    <EscalationCard
                      key={e.id}
                      escalation={e}
                      onChanged={() => mutate()}
                    />
                  ))}
                </div>
              )}
            </section>
          )}
        </>
      )}
    </div>
  );
}
