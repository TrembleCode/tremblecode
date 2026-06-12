"use client";

import { useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { Escalation } from "@/lib/types";
import { Markdown } from "@/components/Markdown";

const TYPE_STYLE: Record<string, string> = {
  milestone_gate: "text-tui-accent border-tui-accent/40",
  destructive_op: "text-tui-danger border-tui-danger/60",
  stuck_agent: "text-tui-danger border-tui-danger/60 animate-flicker",
  question: "text-tui-text border-tui-border",
};

export function EscalationCard({
  escalation,
  projectName,
  onChanged,
}: {
  escalation: Escalation;
  projectName?: string;
  onChanged: () => void;
}) {
  const e = escalation;
  const [response, setResponse] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function respond(option?: string) {
    setBusy(true);
    setError(null);
    try {
      await api.post(`/api/escalations/${e.id}/respond`, {
        response: option ?? response,
        option,
      });
      setResponse("");
      onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "respond failed");
    } finally {
      setBusy(false);
    }
  }

  async function dismiss() {
    setBusy(true);
    setError(null);
    try {
      await api.post(`/api/escalations/${e.id}/dismiss`);
      onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "dismiss failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      className={`border bg-tui-panel p-4 ${
        e.blocking && e.status === "open"
          ? "border-tui-danger/50"
          : "border-tui-border"
      }`}
    >
      <div className="flex flex-wrap items-center gap-2 text-xs font-mono">
        <span
          className={`border px-2 py-0.5 tracking-widest uppercase ${
            TYPE_STYLE[e.type] ?? "text-tui-dim border-tui-border"
          }`}
        >
          [{e.type.replace(/_/g, ".").toUpperCase()}]
        </span>
        {e.blocking && e.status === "open" && (
          <span className="text-tui-danger tracking-widest animate-blink">
            ⚠ BLOCKING
          </span>
        )}
        <span className="text-tui-dim tracking-widest">@{e.agent_name}</span>
        {projectName && (
          <Link
            href={`/projects/${e.project_id}/inbox`}
            className="text-tui-accent tracking-widest hover:text-tui-text"
          >
            [{projectName.toUpperCase()}]
          </Link>
        )}
        <span className="ml-auto text-tui-dim">
          {new Date(e.created_at).toLocaleString([], {
            month: "2-digit",
            day: "2-digit",
            hour: "2-digit",
            minute: "2-digit",
          })}
        </span>
      </div>

      <div className="mt-2 font-display text-xl text-tui-text tracking-widest uppercase">
        {e.topic}
      </div>

      <div className="mt-2">
        <Markdown content={e.body_md} className="text-sm" />
      </div>

      {error && (
        <div className="mt-2 text-xs text-tui-danger font-mono tracking-widest">
          ERR: {error}
        </div>
      )}

      {e.status === "open" ? (
        <div className="mt-3 border-t border-tui-border/40 pt-3 space-y-2">
          {e.options.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {e.options.map((opt) => (
                <button
                  key={opt}
                  onClick={() => respond(opt)}
                  disabled={busy}
                  className="border border-tui-accent/60 text-tui-accent px-3 py-1.5 text-xs font-mono
                             hover:bg-tui-accent/10 disabled:opacity-30 tracking-widest uppercase"
                >
                  ▸ {opt}
                </button>
              ))}
            </div>
          )}
          <div className="flex gap-2 items-end">
            <textarea
              value={response}
              onChange={(ev) => setResponse(ev.target.value)}
              rows={2}
              placeholder="FREE-TEXT RESPONSE..."
              className="tui-input resize-none flex-1"
              spellCheck={false}
            />
            <button
              onClick={() => respond()}
              disabled={busy || !response.trim()}
              className="border border-tui-active/60 text-tui-active px-4 py-2 text-xs font-mono
                         hover:bg-tui-active/10 disabled:opacity-30 tracking-widest uppercase shrink-0"
            >
              {busy ? "..." : "// RESPOND"}
            </button>
            <button
              onClick={dismiss}
              disabled={busy}
              className="border border-tui-border px-4 py-2 text-xs text-tui-dim font-mono
                         hover:text-tui-text disabled:opacity-30 tracking-widest uppercase shrink-0"
            >
              // DISMISS
            </button>
          </div>
        </div>
      ) : (
        e.response_md && (
          <div className="mt-3 border-t border-tui-border/40 pt-2 text-sm font-mono">
            <span className="text-xs text-tui-active tracking-widest uppercase">
              ✓ RESPONSE:{" "}
            </span>
            <span className="text-tui-text">{e.response_md}</span>
          </div>
        )
      )}
    </div>
  );
}
