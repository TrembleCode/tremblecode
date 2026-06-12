"use client";

import { useState } from "react";
import useSWR from "swr";
import { api, fetcher } from "@/lib/api";
import type { AgentTemplate } from "@/lib/types";

const EMPTY: Partial<AgentTemplate> = {
  role_key: "",
  display_name: "",
  description: "",
  system_prompt_md: "",
  model: "sonnet",
  default_count: 1,
  color: "#33ff57",
  kind: "dev",
};

export default function SettingsPage() {
  const { data: templates, mutate } = useSWR<AgentTemplate[]>(
    "/api/agent-templates",
    fetcher
  );
  const [editing, setEditing] = useState<Partial<AgentTemplate> | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function save() {
    if (!editing) return;
    setError(null);
    try {
      if (editing.id) {
        await api.patch(`/api/agent-templates/${editing.id}`, {
          display_name: editing.display_name,
          description: editing.description,
          system_prompt_md: editing.system_prompt_md,
          model: editing.model,
          default_count: editing.default_count,
          color: editing.color,
          kind: editing.kind,
        });
      } else {
        await api.post("/api/agent-templates", editing);
      }
      setEditing(null);
      mutate();
    } catch (e) {
      setError(e instanceof Error ? e.message : "save failed");
    }
  }

  async function remove(id: string) {
    setError(null);
    try {
      await api.delete(`/api/agent-templates/${id}`);
      mutate();
    } catch (e) {
      setError(e instanceof Error ? e.message : "delete failed");
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="font-display text-4xl text-tui-active tracking-widest uppercase">
            Settings
          </h1>
          <div className="mt-1 text-xs text-tui-dim tracking-widest">
            AGENT FIGURES · ROSTER TEMPLATES
          </div>
        </div>
        <button
          onClick={() => setEditing({ ...EMPTY })}
          className="border border-tui-accent/60 text-tui-accent px-4 py-2 text-xs font-mono
                     hover:bg-tui-accent/10 transition-colors tracking-widest uppercase"
        >
          + NEW FIGURE
        </button>
      </div>

      {error && (
        <div className="text-xs text-tui-danger font-mono tracking-widest">ERR: {error}</div>
      )}

      <div className="border border-tui-border divide-y divide-tui-border/40 bg-tui-panel">
        {(templates ?? []).map((t) => (
          <div key={t.id} className="flex items-center gap-3 px-4 py-3">
            <span className="w-2 h-2 shrink-0" style={{ backgroundColor: t.color }} />
            <div className="flex-1 min-w-0">
              <div className="text-sm text-tui-text tracking-wider uppercase">
                {t.display_name}
                {t.is_builtin && (
                  <span className="ml-2 text-xs text-tui-border">[BUILTIN]</span>
                )}
              </div>
              <div className="text-xs text-tui-dim font-mono truncate">
                {t.role_key} · {t.kind} · {t.model} · x{t.default_count}
              </div>
            </div>
            <button
              onClick={() => setEditing(t)}
              className="border border-tui-border px-3 py-1 text-xs text-tui-dim font-mono
                         hover:text-tui-text hover:border-tui-text/40 tracking-widest uppercase"
            >
              EDIT
            </button>
            {!t.is_builtin && (
              <button
                onClick={() => remove(t.id)}
                className="border border-tui-danger/40 px-3 py-1 text-xs text-tui-danger font-mono
                           hover:bg-tui-danger/10 tracking-widest uppercase"
              >
                DEL
              </button>
            )}
          </div>
        ))}
      </div>

      {editing && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-tui-bg/80 backdrop-blur-sm p-6">
          <div className="w-full max-w-2xl border border-tui-border bg-tui-panel p-6 max-h-[90vh] overflow-y-auto">
            <h2 className="font-display text-xl text-tui-active tracking-widest uppercase mb-4">
              {editing.id ? "// EDIT FIGURE" : "// NEW FIGURE"}
            </h2>
            <div className="grid grid-cols-2 gap-4">
              <Field label="Role key (slug)">
                <input
                  disabled={!!editing.id}
                  value={editing.role_key ?? ""}
                  onChange={(e) => setEditing({ ...editing, role_key: e.target.value })}
                  className="tui-input"
                  placeholder="mobile_dev"
                />
              </Field>
              <Field label="Display name">
                <input
                  value={editing.display_name ?? ""}
                  onChange={(e) =>
                    setEditing({ ...editing, display_name: e.target.value })
                  }
                  className="tui-input"
                />
              </Field>
              <Field label="Kind">
                <select
                  value={editing.kind}
                  onChange={(e) =>
                    setEditing({ ...editing, kind: e.target.value as AgentTemplate["kind"] })
                  }
                  className="tui-input"
                >
                  <option value="lead">lead</option>
                  <option value="dev">dev</option>
                  <option value="qa">qa</option>
                </select>
              </Field>
              <Field label="Model">
                <input
                  value={editing.model ?? ""}
                  onChange={(e) => setEditing({ ...editing, model: e.target.value })}
                  className="tui-input"
                  placeholder="sonnet | opus | haiku"
                />
              </Field>
              <Field label="Default count">
                <input
                  type="number"
                  min={0}
                  max={4}
                  value={editing.default_count ?? 1}
                  onChange={(e) =>
                    setEditing({
                      ...editing,
                      default_count: parseInt(e.target.value || "0", 10),
                    })
                  }
                  className="tui-input"
                />
              </Field>
              <Field label="Color">
                <input
                  value={editing.color ?? ""}
                  onChange={(e) => setEditing({ ...editing, color: e.target.value })}
                  className="tui-input"
                  placeholder="#33ff57"
                />
              </Field>
            </div>
            <Field label="Description">
              <input
                value={editing.description ?? ""}
                onChange={(e) => setEditing({ ...editing, description: e.target.value })}
                className="tui-input"
              />
            </Field>
            <Field label="System prompt (markdown)">
              <textarea
                rows={12}
                value={editing.system_prompt_md ?? ""}
                onChange={(e) =>
                  setEditing({ ...editing, system_prompt_md: e.target.value })
                }
                className="tui-input font-mono"
                spellCheck={false}
              />
            </Field>
            <div className="flex justify-end gap-3 pt-4 border-t border-tui-border/40 mt-4">
              <button
                onClick={() => setEditing(null)}
                className="border border-tui-border px-4 py-2 text-xs text-tui-dim font-mono
                           hover:text-tui-text tracking-widest uppercase"
              >
                // ABORT
              </button>
              <button
                onClick={save}
                className="border border-tui-accent/60 text-tui-accent px-4 py-2 text-xs font-mono
                           hover:bg-tui-accent/10 tracking-widest uppercase"
              >
                // SAVE
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="mt-3">
      <label className="block text-xs text-tui-dim tracking-widest uppercase mb-1">
        {label}
      </label>
      {children}
    </div>
  );
}
