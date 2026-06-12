"use client";

import { useState } from "react";
import useSWR from "swr";
import { fetcher } from "@/lib/api";
import type { Project } from "@/lib/types";
import { ProjectCard } from "@/components/ProjectCard";
import { CreateProjectDialog } from "@/components/CreateProjectDialog";
import { useAfSocket } from "@/components/WebSocketProvider";

export default function HomePage() {
  const { data: projects, mutate } = useSWR<Project[]>("/api/projects", fetcher);
  const { connected } = useAfSocket();
  const [showArchived, setShowArchived] = useState(false);

  const active = (projects ?? []).filter((p) => !p.archived);
  const archived = (projects ?? []).filter((p) => p.archived);

  return (
    <div>
      <div className="flex items-start justify-between">
        <div>
          <h1 className="font-display text-4xl text-tui-active tracking-widest uppercase">
            Projects
          </h1>
          <div className="mt-1 text-xs text-tui-dim tracking-widest">
            LINK: {connected ? "ESTABLISHED" : "DOWN"} · UNITS: {active.length}
          </div>
        </div>
        <CreateProjectDialog onCreated={() => mutate()} />
      </div>

      <div className="mt-6 grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {active.map((p) => (
          <ProjectCard key={p.id} project={p} onChanged={() => mutate()} />
        ))}
      </div>

      {projects && active.length === 0 && (
        <div className="mt-8 border border-tui-border bg-tui-panel p-8 text-center text-tui-dim">
          <div className="font-display text-2xl tracking-widest">NO PROJECTS</div>
          <div className="mt-2 text-xs tracking-widest">
            INITIATE A NEW PROJECT TO DEPLOY YOUR FIRST AGENT TEAM
          </div>
        </div>
      )}

      {archived.length > 0 && (
        <div className="mt-10">
          <button
            type="button"
            onClick={() => setShowArchived((v) => !v)}
            className="flex items-center gap-2 font-display text-sm text-tui-dim tracking-widest uppercase hover:text-tui-text transition-colors"
          >
            <span>{showArchived ? "▾" : "▸"}</span>
            Archived Projects
            <span className="text-tui-border">[{archived.length}]</span>
          </button>

          {showArchived && (
            <div className="mt-4 grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 opacity-70">
              {archived.map((p) => (
                <ProjectCard key={p.id} project={p} onChanged={() => mutate()} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
