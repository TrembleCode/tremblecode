"use client";

import useSWR from "swr";
import { fetcher } from "@/lib/api";
import type { ProjectDetail } from "@/lib/types";
import { StatusBadge } from "@/components/StatusBadge";
import { ProjectNav } from "@/components/ProjectNav";

/** Page header + sub-nav used by every project subpage. */
export function ProjectHeader({
  projectId,
  section,
}: {
  projectId: string;
  section: string;
}) {
  const { data: project } = useSWR<ProjectDetail>(
    `/api/projects/${projectId}`,
    fetcher
  );

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="font-display text-4xl text-tui-active tracking-widest uppercase">
            {project?.name ?? "..."}
          </h1>
          <div className="mt-1 text-xs text-tui-dim tracking-widest font-mono uppercase">
            // {section}
          </div>
        </div>
        {project && <StatusBadge status={project.status} />}
      </div>
      <ProjectNav projectId={projectId} />
    </div>
  );
}
