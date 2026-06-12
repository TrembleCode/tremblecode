"use client";

import { useState, useEffect } from "react";
import { marked } from "marked";
import { api } from "@/lib/api";

type EditorMode = "WRITE" | "PREVIEW";

interface Props {
  projectId: string;
  initialContent: string;
  onSaved?: () => void;
}

export function PrdEditor({ projectId, initialContent, onSaved }: Props) {
  const [mode, setMode] = useState<EditorMode>("WRITE");
  const [content, setContent] = useState(initialContent);
  const [savedContent, setSavedContent] = useState(initialContent);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveOk, setSaveOk] = useState(false);
  const [renderedHtml, setRenderedHtml] = useState("");

  const hasUnsavedChanges = content !== savedContent;

  useEffect(() => {
    setContent(initialContent);
    setSavedContent(initialContent);
  }, [initialContent]);

  useEffect(() => {
    if (mode !== "PREVIEW") return;
    setRenderedHtml(marked(content || "") as string);
  }, [mode, content]);

  async function handleSave() {
    setSaving(true);
    setSaveError(null);
    setSaveOk(false);
    try {
      await api.put(`/api/projects/${projectId}/prd`, { prd_md: content });
      setSavedContent(content);
      setSaveOk(true);
      onSaved?.();
      setTimeout(() => setSaveOk(false), 2000);
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="border border-tui-border bg-tui-panel">
      <div className="flex items-center justify-between px-4 py-2 border-b border-tui-border">
        <div className="font-display text-lg text-tui-active tracking-widest uppercase">
          // PRD EDITOR
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setMode(mode === "WRITE" ? "PREVIEW" : "WRITE")}
            className="border border-tui-border text-tui-dim hover:text-tui-text hover:border-tui-text/60
                       px-3 py-1 text-xs font-mono tracking-widest uppercase transition-colors"
          >
            {mode === "WRITE" ? "// PREVIEW" : "// WRITE"}
          </button>
          <button
            onClick={handleSave}
            disabled={saving || !hasUnsavedChanges}
            className="border border-tui-accent/60 text-tui-accent hover:bg-tui-accent/10
                       disabled:opacity-30 px-3 py-1 text-xs font-mono tracking-widest uppercase transition-colors"
          >
            {saving ? "SAVING..." : saveOk ? "SAVED ✓" : "// SAVE"}
          </button>
        </div>
      </div>

      {hasUnsavedChanges && (
        <div className="px-4 py-1 text-xs text-tui-accent font-mono tracking-widest border-b border-tui-border/40 animate-flicker">
          ⚠ UNSAVED CHANGES
        </div>
      )}

      {saveError && (
        <div className="px-4 py-1 text-xs text-tui-danger font-mono tracking-widest border-b border-tui-border/40">
          ERR: {saveError}
        </div>
      )}

      {mode === "WRITE" && (
        <textarea
          value={content}
          onChange={(e) => setContent(e.target.value)}
          rows={20}
          className="w-full bg-tui-bg text-tui-text font-mono text-sm p-4 resize-none
                     focus:outline-none focus:ring-1 focus:ring-tui-active/40
                     placeholder:text-tui-border"
          placeholder={"# PROJECT REQUIREMENTS DOCUMENT\n\nEnter your PRD in Markdown format..."}
          spellCheck={false}
        />
      )}

      {mode === "PREVIEW" && (
        <div className="p-6 min-h-80">
          {renderedHtml ? (
            <div className="tui-prose" dangerouslySetInnerHTML={{ __html: renderedHtml }} />
          ) : (
            <p className="text-tui-border font-mono text-sm tracking-widest">
              NO CONTENT TO PREVIEW
              <span className="animate-blink ml-1">▮</span>
            </p>
          )}
        </div>
      )}
    </section>
  );
}
