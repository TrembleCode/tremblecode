"use client";

import useSWR from "swr";
import { fetcher } from "@/lib/api";
import type { Project } from "@/lib/types";
import { ProjectCard } from "@/components/ProjectCard";
import { CreateProjectDialog } from "@/components/CreateProjectDialog";
import { useAfSocket } from "@/components/WebSocketProvider";

export default function HomePage() {
  const { data: projects, mutate } = useSWR<Project[]>("/api/projects", fetcher);
  const { connected } = useAfSocket();

  return (
    <div>
      <div className="flex items-start justify-between">
        <div>
          <h1 className="font-display text-4xl text-tui-active tracking-widest uppercase">
            Projects
          </h1>
          <div className="mt-1 text-xs text-tui-dim tracking-widest">
            LINK: {connected ? "ESTABLISHED" : "DOWN"} · UNITS:{" "}
            {projects?.length ?? "—"}
          </div>
        </div>
        <CreateProjectDialog onCreated={() => mutate()} />
      </div>

      <div className="mt-6 grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {(projects ?? []).map((p) => (
          <ProjectCard key={p.id} project={p} />
        ))}
      </div>

      {projects && projects.length === 0 && (
        <div className="mt-8 border border-tui-border bg-tui-panel p-8 text-center text-tui-dim">
          <div className="font-display text-2xl tracking-widest">NO PROJECTS</div>
          <div className="mt-2 text-xs tracking-widest">
            INITIATE A NEW PROJECT TO DEPLOY YOUR FIRST AGENT TEAM
          </div>
        </div>
      )}
    </div>
  );
}
