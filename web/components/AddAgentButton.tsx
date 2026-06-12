"use client";

import { useState } from "react";
import useSWR from "swr";
import { api, fetcher } from "@/lib/api";
import type { AgentTemplate } from "@/lib/types";

export function AddAgentButton({
  projectId,
  onAdded,
}: {
  projectId: string;
  onAdded: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [roleKey, setRoleKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { data: templates } = useSWR<AgentTemplate[]>(
    open ? "/api/agent-templates" : null,
    fetcher
  );

  const options = (templates ?? []).filter((t) => t.kind !== "lead");

  async function submit() {
    if (!roleKey) return;
    setBusy(true);
    setError(null);
    try {
      await api.post(`/api/projects/${projectId}/agents`, { role_key: roleKey });
      setOpen(false);
      setRoleKey("");
      onAdded();
    } catch (e) {
      setError(e instanceof Error ? e.message : "failed");
    } finally {
      setBusy(false);
    }
  }

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="border border-tui-accent/60 text-tui-accent px-3 py-1 text-xs font-mono
                   hover:bg-tui-accent/10 transition-colors tracking-widest uppercase"
      >
        + ADD AGENT
      </button>
    );
  }

  return (
    <span className="inline-flex items-center gap-2">
      <select
        autoFocus
        value={roleKey}
        onChange={(e) => setRoleKey(e.target.value)}
        className="border border-tui-border bg-tui-bg px-2 py-1 text-xs text-tui-text font-mono
                   focus:border-tui-active focus:outline-none"
      >
        <option value="">select figure…</option>
        {options.map((t) => (
          <option key={t.id} value={t.role_key}>
            {t.display_name} ({t.model})
          </option>
        ))}
      </select>
      <button
        onClick={submit}
        disabled={busy || !roleKey}
        className="border border-tui-active/60 text-tui-active px-3 py-1 text-xs font-mono
                   hover:bg-tui-active/10 disabled:opacity-30 tracking-widest uppercase"
      >
        {busy ? "..." : "// DEPLOY"}
      </button>
      <button
        onClick={() => {
          setOpen(false);
          setError(null);
        }}
        className="border border-tui-border px-3 py-1 text-xs text-tui-dim font-mono
                   hover:text-tui-text tracking-widest uppercase"
      >
        ABORT
      </button>
      {error && (
        <span className="text-xs text-tui-danger font-mono tracking-wider">
          ERR: {error}
        </span>
      )}
    </span>
  );
}
