"use client";

import { useState } from "react";
import useSWR from "swr";
import { api, fetcher } from "@/lib/api";
import type { McpSuggestion } from "@/lib/types";

const STATUS_STYLE: Record<McpSuggestion["status"], string> = {
  proposed: "text-tui-accent border-tui-accent/40",
  approved: "text-tui-active border-tui-active/40",
  installed: "text-tui-active border-tui-active/60",
  rejected: "text-tui-dim border-tui-border",
};

/** MCP suggestion list — endpoint may not exist yet, so failures render an empty state. */
export function McpTab({ projectId }: { projectId: string }) {
  const { data, error, isLoading, mutate } = useSWR<McpSuggestion[]>(
    `/api/projects/${projectId}/mcp-suggestions`,
    fetcher,
    { shouldRetryOnError: false }
  );
  const [approving, setApproving] = useState<string | null>(null);
  const [envValues, setEnvValues] = useState<Record<string, string>>({});
  const [actionError, setActionError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (isLoading) {
    return (
      <div className="text-tui-dim font-mono text-sm tracking-widest animate-flicker">
        LOADING MCP SUGGESTIONS...
      </div>
    );
  }

  const suggestions = error ? [] : data ?? [];

  if (suggestions.length === 0) {
    return (
      <div className="border border-tui-border bg-tui-panel p-8 text-center text-tui-dim">
        <div className="font-display text-2xl tracking-widest">
          NO MCP SUGGESTIONS
        </div>
        <div className="mt-2 text-xs tracking-widest font-mono">
          the team lead will propose MCP servers as needs emerge
        </div>
      </div>
    );
  }

  async function approve(s: McpSuggestion) {
    setBusy(true);
    setActionError(null);
    try {
      await api.post(`/api/mcp-suggestions/${s.id}/approve`, {
        env_values: envValues,
      });
      setApproving(null);
      setEnvValues({});
      mutate();
    } catch (e) {
      setActionError(e instanceof Error ? e.message : "approve failed");
    } finally {
      setBusy(false);
    }
  }

  async function reject(s: McpSuggestion) {
    setBusy(true);
    setActionError(null);
    try {
      await api.post(`/api/mcp-suggestions/${s.id}/reject`);
      mutate();
    } catch (e) {
      setActionError(e instanceof Error ? e.message : "reject failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-3">
      {actionError && (
        <div className="text-xs text-tui-danger font-mono tracking-widest">
          ERR: {actionError}
        </div>
      )}
      {suggestions.map((s) => (
        <div key={s.id} className="border border-tui-border bg-tui-panel p-4">
          <div className="flex items-center gap-3">
            <span className="font-display text-lg text-tui-text tracking-widest uppercase">
              {s.name}
            </span>
            <span
              className={`px-2 py-0.5 text-xs font-mono border tracking-widest ${STATUS_STYLE[s.status]}`}
            >
              [{s.status.toUpperCase()}]
            </span>
            {s.status === "proposed" && (
              <div className="ml-auto flex gap-2">
                <button
                  onClick={() => {
                    if (s.env_keys.length === 0) {
                      setEnvValues({});
                      approve(s);
                    } else {
                      setApproving(approving === s.id ? null : s.id);
                      setEnvValues({});
                    }
                  }}
                  disabled={busy}
                  className="border border-tui-active/60 text-tui-active px-3 py-1 text-xs font-mono
                             hover:bg-tui-active/10 disabled:opacity-30 tracking-widest uppercase"
                >
                  // APPROVE
                </button>
                <button
                  onClick={() => reject(s)}
                  disabled={busy}
                  className="border border-tui-danger/40 text-tui-danger px-3 py-1 text-xs font-mono
                             hover:bg-tui-danger/10 disabled:opacity-30 tracking-widest uppercase"
                >
                  // REJECT
                </button>
              </div>
            )}
          </div>
          <div className="mt-2 text-sm text-tui-dim font-mono">{s.reason}</div>
          {s.env_keys.length > 0 && (
            <div className="mt-2 text-xs text-tui-dim font-mono tracking-widest">
              ENV: {s.env_keys.join(" · ")}
            </div>
          )}
          {approving === s.id && (
            <div className="mt-3 border-t border-tui-border/40 pt-3 space-y-2">
              <div className="text-xs text-tui-accent tracking-widest font-mono uppercase">
                ── ENVIRONMENT VARIABLES REQUIRED ──
              </div>
              {s.env_keys.map((k) => (
                <div key={k} className="flex items-center gap-2">
                  <label className="w-48 shrink-0 text-xs text-tui-dim font-mono tracking-widest">
                    {k}
                  </label>
                  <input
                    type="password"
                    value={envValues[k] ?? ""}
                    onChange={(e) =>
                      setEnvValues({ ...envValues, [k]: e.target.value })
                    }
                    className="tui-input"
                    spellCheck={false}
                  />
                </div>
              ))}
              <div className="flex justify-end">
                <button
                  onClick={() => approve(s)}
                  disabled={busy || s.env_keys.some((k) => !envValues[k])}
                  className="border border-tui-active/60 text-tui-active px-4 py-2 text-xs font-mono
                             hover:bg-tui-active/10 disabled:opacity-30 tracking-widest uppercase"
                >
                  {busy ? "INSTALLING..." : "// CONFIRM APPROVE"}
                </button>
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
