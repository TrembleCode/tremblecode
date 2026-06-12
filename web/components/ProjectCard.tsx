import Link from "next/link";
import type { Project } from "@/lib/types";
import { StatusBadge } from "./StatusBadge";

export function ProjectCard({ project }: { project: Project }) {
  return (
    <Link
      href={`/projects/${project.id}`}
      className="block border border-tui-border bg-tui-panel p-4
                 hover:border-tui-text/50 transition-colors
                 group relative overflow-hidden"
    >
      <span className="absolute top-0 left-0 text-tui-border text-xs select-none leading-none group-hover:text-tui-dim transition-colors">┌</span>
      <span className="absolute top-0 right-0 text-tui-border text-xs select-none leading-none group-hover:text-tui-dim transition-colors">┐</span>
      <span className="absolute bottom-0 left-0 text-tui-border text-xs select-none leading-none group-hover:text-tui-dim transition-colors">└</span>
      <span className="absolute bottom-0 right-0 text-tui-border text-xs select-none leading-none group-hover:text-tui-dim transition-colors">┘</span>

      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="min-w-0">
          <h2 className="truncate text-base font-display text-tui-active tracking-widest uppercase group-hover:animate-glitch">
            {project.name}
          </h2>
          <p className="text-xs text-tui-dim font-mono mt-0.5">{project.slug}</p>
        </div>
        <StatusBadge status={project.status} />
      </div>

      {project.description && (
        <p className="text-xs text-tui-dim line-clamp-2 mb-3">{project.description}</p>
      )}

      <div className="flex items-center gap-4 text-xs text-tui-dim border-t border-tui-border/40 pt-2 mt-2">
        <span>{new Date(project.created_at).toLocaleDateString()}</span>
        {project.container_id && (
          <span className="flex items-center gap-1 text-tui-active">
            <span className="animate-blink">▮</span>
            SANDBOX.UP
          </span>
        )}
      </div>
    </Link>
  );
}
