"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import useSWR from "swr";
import { api, fetcher } from "@/lib/api";
import type { AgentTemplate, Project } from "@/lib/types";

export function CreateProjectDialog({ onCreated }: { onCreated: () => void }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [withDiscussion, setWithDiscussion] = useState(true);
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { data: templates } = useSWR<AgentTemplate[]>(
    open ? "/api/agent-templates" : null,
    fetcher
  );

  function countFor(t: AgentTemplate) {
    return counts[t.role_key] ?? t.default_count;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const roster = (templates ?? [])
        .map((t) => ({ role_key: t.role_key, count: countFor(t) }))
        .filter((r) => r.count > 0);
      const project = await api.post<Project>("/api/projects", {
        name: name.trim(),
        description: description.trim(),
        roster,
        start_with_discussion: withDiscussion,
      });
      setOpen(false);
      onCreated();
      router.push(`/projects/${project.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create project");
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="border border-tui-accent/60 text-tui-accent px-4 py-2 text-xs font-mono
                   hover:bg-tui-accent/10 transition-colors tracking-widest uppercase"
      >
        + NEW PROJECT
      </button>

      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-tui-bg/80 backdrop-blur-sm">
          <div className="w-full max-w-lg border border-tui-border bg-tui-panel p-6 shadow-2xl max-h-[90vh] overflow-y-auto">
            <h2 className="font-display text-xl text-tui-active tracking-widest uppercase mb-1">
              // INIT NEW PROJECT
            </h2>
            <div className="text-xs text-tui-border tracking-widest mb-5">
              ── Enter project parameters ──
            </div>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-xs text-tui-dim tracking-widest uppercase mb-1">
                  Project Name *
                </label>
                <input
                  autoFocus
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full border border-tui-border bg-tui-bg px-3 py-2 text-sm text-tui-text font-mono
                             focus:border-tui-active focus:outline-none tracking-wide"
                  placeholder="my-awesome-project"
                />
              </div>
              <div>
                <label className="block text-xs text-tui-dim tracking-widest uppercase mb-1">
                  Description
                </label>
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  rows={2}
                  className="w-full border border-tui-border bg-tui-bg px-3 py-2 text-sm text-tui-text font-mono
                             focus:border-tui-active focus:outline-none resize-none tracking-wide"
                  placeholder="What are you building?"
                />
              </div>

              {/* Roster picker */}
              <div>
                <label className="block text-xs text-tui-dim tracking-widest uppercase mb-1">
                  Team Roster
                </label>
                <div className="border border-tui-border divide-y divide-tui-border/40">
                  {(templates ?? []).map((t) => (
                    <div key={t.id} className="flex items-center gap-3 px-3 py-2">
                      <span
                        className="w-2 h-2 shrink-0"
                        style={{ backgroundColor: t.color }}
                      />
                      <span className="text-xs text-tui-text tracking-wider flex-1 uppercase">
                        {t.display_name}
                      </span>
                      <span className="text-xs text-tui-dim">{t.model}</span>
                      <input
                        type="number"
                        min={t.kind === "lead" ? 1 : 0}
                        max={t.kind === "lead" ? 1 : 4}
                        value={countFor(t)}
                        onChange={(e) =>
                          setCounts({
                            ...counts,
                            [t.role_key]: parseInt(e.target.value || "0", 10),
                          })
                        }
                        className="w-14 border border-tui-border bg-tui-bg px-2 py-1 text-xs text-tui-text
                                   font-mono focus:border-tui-active focus:outline-none text-center"
                      />
                    </div>
                  ))}
                  {!templates && (
                    <div className="px-3 py-2 text-xs text-tui-dim animate-flicker">
                      LOADING ROSTER...
                    </div>
                  )}
                </div>
              </div>

              <label className="flex items-center gap-2 text-xs text-tui-dim tracking-widest uppercase cursor-pointer">
                <input
                  type="checkbox"
                  checked={withDiscussion}
                  onChange={(e) => setWithDiscussion(e.target.checked)}
                  className="accent-current"
                />
                Start with planning discussion (no PRD yet)
              </label>

              {error && (
                <p className="text-xs text-tui-danger font-mono tracking-widest">{error}</p>
              )}
              <div className="flex justify-end gap-3 pt-2 border-t border-tui-border/40">
                <button
                  type="button"
                  onClick={() => setOpen(false)}
                  className="border border-tui-border px-4 py-2 text-xs text-tui-dim font-mono
                             hover:text-tui-text hover:border-tui-text/40 transition-colors tracking-widest uppercase"
                >
                  // ABORT
                </button>
                <button
                  type="submit"
                  disabled={loading || !name.trim()}
                  className="border border-tui-accent/60 text-tui-accent px-4 py-2 text-xs font-mono
                             hover:bg-tui-accent/10 disabled:opacity-30 transition-colors tracking-widest uppercase"
                >
                  {loading ? "INITIALIZING..." : "// EXECUTE"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
}
