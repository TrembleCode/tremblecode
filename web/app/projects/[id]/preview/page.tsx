"use client";

import { use, useEffect, useState } from "react";
import useSWR from "swr";
import { fetcher } from "@/lib/api";
import type { ServiceInfo } from "@/lib/types";
import { ProjectHeader } from "@/components/ProjectHeader";

export default function PreviewPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const { data: services, error } = useSWR<ServiceInfo[]>(
    `/api/projects/${id}/services`,
    fetcher,
    { shouldRetryOnError: false }
  );
  const [active, setActive] = useState<string | null>(null);

  const list = error ? [] : services ?? [];
  const current = list.find((s) => s.id === active) ?? list[0];

  useEffect(() => {
    if (!active && list.length > 0) setActive(list[0].id);
  }, [active, list]);

  return (
    <div className="flex flex-col h-full space-y-4">
      <ProjectHeader projectId={id} section="PREVIEW · DEV SERVERS" />

      {!services && !error ? (
        <div className="text-tui-dim font-mono text-sm tracking-widest animate-flicker">
          SCANNING PORTS...
        </div>
      ) : list.length === 0 ? (
        <div className="border border-tui-border bg-tui-panel p-12 text-center text-tui-dim">
          <div className="font-display text-2xl tracking-widest">
            NO SIGNAL
          </div>
          <div className="mt-2 text-xs tracking-widest font-mono">
            no dev servers registered yet — agents expose them as they build
          </div>
        </div>
      ) : (
        <div className="flex-1 min-h-0 flex flex-col border border-tui-border bg-tui-panel">
          {/* Service tabs */}
          <div className="flex flex-wrap items-center gap-1 px-2 pt-2 border-b border-tui-border">
            {list.map((s) => (
              <button
                key={s.id}
                onClick={() => setActive(s.id)}
                className={`px-4 py-2 text-xs font-mono tracking-widest uppercase border-b-2 -mb-px transition-colors ${
                  current?.id === s.id
                    ? "border-tui-active text-tui-active"
                    : "border-transparent text-tui-dim hover:text-tui-text"
                }`}
              >
                {s.name} <span className="text-tui-border">:{s.host_port}</span>
                {s.status !== "running" && s.status !== "up" && (
                  <span className="ml-1 text-tui-danger">
                    [{s.status.toUpperCase()}]
                  </span>
                )}
              </button>
            ))}
            {current && (
              <a
                href={`http://localhost:${current.host_port}`}
                target="_blank"
                rel="noopener noreferrer"
                className="ml-auto mb-1 border border-tui-accent/60 text-tui-accent px-3 py-1 text-xs font-mono
                           hover:bg-tui-accent/10 tracking-widest uppercase"
              >
                OPEN ↗
              </a>
            )}
          </div>
          {/* Frame */}
          {current && (
            <div className="flex-1 min-h-0 bg-tui-bg">
              <div className="px-3 py-1 text-xs text-tui-dim font-mono tracking-widest border-b border-tui-border/40">
                http://localhost:{current.host_port} · via @{current.agent_name}{" "}
                · container :{current.container_port}
              </div>
              <iframe
                key={current.id}
                src={`http://localhost:${current.host_port}`}
                sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-modals"
                className="w-full h-[calc(100%-1.75rem)] bg-white"
                title={current.name}
              />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
