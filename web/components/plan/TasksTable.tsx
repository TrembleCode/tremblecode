"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import type { Milestone, Task } from "@/lib/types";
import { StatusBadge } from "@/components/StatusBadge";

type EditableField = "title" | "role_key" | "estimate_h" | "dependencies";

export function TasksTable({
  tasks,
  milestones,
  editable,
  onSaved,
}: {
  tasks: Task[];
  milestones: Milestone[];
  editable: boolean;
  onSaved: () => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const msByid = new Map(milestones.map((m) => [m.id, m]));

  if (tasks.length === 0) {
    return (
      <div className="border border-tui-border bg-tui-panel p-8 text-center text-tui-dim text-xs tracking-widest font-mono">
        NO TASKS IN THIS PLAN
      </div>
    );
  }

  async function saveField(task: Task, field: EditableField, raw: string) {
    setError(null);
    let value: unknown = raw;
    if (field === "estimate_h") {
      value = raw === "" ? null : Number(raw);
      if (value !== null && Number.isNaN(value)) {
        setError("estimate must be a number");
        return false;
      }
    }
    if (field === "dependencies") {
      value = raw
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
    }
    try {
      await api.patch(`/api/tasks/${task.id}`, { [field]: value });
      onSaved();
      return true;
    } catch (e) {
      setError(e instanceof Error ? e.message : "save failed");
      return false;
    }
  }

  return (
    <div className="space-y-2">
      {editable && (
        <div className="text-xs text-tui-dim tracking-widest font-mono">
          ── CLICK A CELL TO EDIT · ENTER SAVES · ESC CANCELS ── (PENDING tasks
          only)
        </div>
      )}
      {error && (
        <div className="text-xs text-tui-danger font-mono tracking-widest">
          ERR: {error}
        </div>
      )}
      <div className="border border-tui-border bg-tui-panel overflow-x-auto">
        <table className="w-full text-sm font-mono">
          <thead>
            <tr className="text-xs text-tui-dim tracking-widest uppercase border-b border-tui-border">
              <th className="text-left px-3 py-2">KEY</th>
              <th className="text-left px-3 py-2">TITLE</th>
              <th className="text-left px-3 py-2">ROLE</th>
              <th className="text-left px-3 py-2">MILESTONE</th>
              <th className="text-left px-3 py-2">DEPS</th>
              <th className="text-right px-3 py-2">EST.H</th>
              <th className="text-left px-3 py-2">STATUS</th>
            </tr>
          </thead>
          <tbody>
            {tasks.map((t) => {
              const rowEditable = editable && t.status === "PENDING";
              return (
                <tr
                  key={t.id}
                  className="border-b border-tui-border/40 hover:bg-tui-border/20"
                >
                  <td className="px-3 py-2 text-tui-accent whitespace-nowrap">
                    {t.task_key}
                  </td>
                  <Cell
                    value={t.title}
                    editable={rowEditable}
                    onSave={(v) => saveField(t, "title", v)}
                    className="text-tui-text"
                  />
                  <Cell
                    value={t.role_key}
                    editable={rowEditable}
                    onSave={(v) => saveField(t, "role_key", v)}
                    className="text-tui-dim"
                  />
                  <td className="px-3 py-2 text-tui-dim whitespace-nowrap">
                    {t.milestone_id
                      ? msByid.get(t.milestone_id)?.key ?? "?"
                      : "—"}
                  </td>
                  <Cell
                    value={(t.dependencies ?? []).join(", ")}
                    editable={rowEditable}
                    onSave={(v) => saveField(t, "dependencies", v)}
                    className="text-tui-dim"
                    placeholder="—"
                  />
                  <Cell
                    value={t.estimate_h != null ? String(t.estimate_h) : ""}
                    editable={rowEditable}
                    onSave={(v) => saveField(t, "estimate_h", v)}
                    className="text-tui-text text-right"
                    placeholder="—"
                  />
                  <td className="px-3 py-2 whitespace-nowrap">
                    <StatusBadge status={t.status} />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Cell({
  value,
  editable,
  onSave,
  className,
  placeholder,
}: {
  value: string;
  editable: boolean;
  onSave: (v: string) => Promise<boolean>;
  className?: string;
  placeholder?: string;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);
  const [saving, setSaving] = useState(false);

  if (!editing) {
    return (
      <td
        className={`px-3 py-2 ${className ?? ""} ${
          editable ? "cursor-pointer hover:text-tui-active" : ""
        }`}
        onClick={() => {
          if (editable) {
            setDraft(value);
            setEditing(true);
          }
        }}
        title={editable ? "click to edit" : undefined}
      >
        {value || <span className="text-tui-border">{placeholder ?? ""}</span>}
      </td>
    );
  }

  return (
    <td className="px-1 py-1">
      <input
        autoFocus
        value={draft}
        disabled={saving}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={async (e) => {
          if (e.key === "Enter") {
            setSaving(true);
            const ok = await onSave(draft);
            setSaving(false);
            if (ok) setEditing(false);
          } else if (e.key === "Escape") {
            setEditing(false);
          }
        }}
        onBlur={() => setEditing(false)}
        className="w-full min-w-24 border border-tui-active/60 bg-tui-bg px-2 py-1 text-sm
                   text-tui-text font-mono focus:outline-none"
        spellCheck={false}
      />
    </td>
  );
}
