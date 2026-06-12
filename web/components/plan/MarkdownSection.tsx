"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Markdown } from "@/components/Markdown";

/** SPECS / RISKS tab: rendered markdown with an EDIT toggle (draft plans only). */
export function MarkdownSection({
  planId,
  field,
  content,
  editable,
  onSaved,
}: {
  planId: string;
  field: "specs_md" | "risks_md";
  content: string;
  editable: boolean;
  onSaved: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(content);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!editing) setDraft(content);
  }, [content, editing]);

  async function save() {
    setSaving(true);
    setError(null);
    try {
      await api.patch(`/api/plans/${planId}`, { [field]: draft });
      setEditing(false);
      onSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : "save failed");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="border border-tui-border bg-tui-panel">
      <div className="flex items-center justify-between px-4 py-2 border-b border-tui-border">
        <span className="text-xs text-tui-dim tracking-widest font-mono uppercase">
          {field === "specs_md" ? "TECHNICAL SPECIFICATIONS" : "RISK REGISTER"}
        </span>
        {editable && (
          <div className="flex gap-2">
            {editing && (
              <button
                onClick={() => {
                  setEditing(false);
                  setDraft(content);
                }}
                className="border border-tui-border px-3 py-1 text-xs text-tui-dim font-mono
                           hover:text-tui-text tracking-widest uppercase"
              >
                // ABORT
              </button>
            )}
            <button
              onClick={() => (editing ? save() : setEditing(true))}
              disabled={saving}
              className="border border-tui-accent/60 text-tui-accent px-3 py-1 text-xs font-mono
                         hover:bg-tui-accent/10 disabled:opacity-30 tracking-widest uppercase"
            >
              {saving ? "SAVING..." : editing ? "// SAVE" : "// EDIT"}
            </button>
          </div>
        )}
      </div>
      {error && (
        <div className="px-4 py-1 text-xs text-tui-danger font-mono tracking-widest border-b border-tui-border/40">
          ERR: {error}
        </div>
      )}
      {editing ? (
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          rows={24}
          className="w-full bg-tui-bg text-tui-text font-mono text-sm p-4 resize-none
                     focus:outline-none focus:ring-1 focus:ring-tui-active/40"
          spellCheck={false}
        />
      ) : (
        <div className="p-6">
          <Markdown content={content} />
        </div>
      )}
    </div>
  );
}
