"use client";

import { use, useEffect, useRef, useState } from "react";
import useSWR from "swr";
import { api, fetcher } from "@/lib/api";
import type { DiscussionMessage, ProjectDetail } from "@/lib/types";
import { ProjectHeader } from "@/components/ProjectHeader";
import { PrdEditor } from "@/components/PrdEditor";
import { Markdown } from "@/components/Markdown";

export default function PrdPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const { data: project, mutate: mutateProject } = useSWR<ProjectDetail>(
    `/api/projects/${id}`,
    fetcher
  );
  const { data: messages, mutate } = useSWR<DiscussionMessage[]>(
    `/api/projects/${id}/discussion`,
    fetcher
  );

  const [draft, setDraft] = useState("");
  const [pending, setPending] = useState(false);
  const [finalizing, setFinalizing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages?.length, pending]);

  async function send() {
    const content = draft.trim();
    if (!content || pending) return;
    setDraft("");
    setError(null);
    setPending(true);
    // optimistic: show the user message immediately
    mutate(
      (cur) => [
        ...(cur ?? []),
        {
          id: `tmp-${Date.now()}`,
          role: "user" as const,
          content,
          created_at: new Date().toISOString(),
        },
      ],
      { revalidate: false }
    );
    try {
      await api.post<DiscussionMessage>(
        `/api/projects/${id}/discussion/messages`,
        { content }
      );
      await mutate();
    } catch (e) {
      setError(e instanceof Error ? e.message : "send failed");
      await mutate();
    } finally {
      setPending(false);
    }
  }

  async function finalize() {
    setFinalizing(true);
    setError(null);
    try {
      await api.post<{ prd_md: string }>(
        `/api/projects/${id}/discussion/finalize`
      );
      await mutateProject();
    } catch (e) {
      setError(e instanceof Error ? e.message : "finalize failed");
    } finally {
      setFinalizing(false);
    }
  }

  return (
    <div className="flex flex-col h-full space-y-4">
      <ProjectHeader projectId={id} section="PRD · REQUIREMENTS & INTERVIEW" />

      <div className="flex-1 min-h-0 grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* ── PRD document ── */}
        <div className="min-h-0 overflow-y-auto">
          {project ? (
            <PrdEditor
              projectId={id}
              initialContent={project.prd_md}
              onSaved={() => mutateProject()}
            />
          ) : (
            <div className="text-tui-dim font-mono text-sm tracking-widest animate-flicker">
              LOADING PRD...
            </div>
          )}
        </div>

        {/* ── Planning interview ── */}
        <div className="flex flex-col min-h-0 border border-tui-border bg-tui-panel">
          <div className="px-4 py-2 border-b border-tui-border flex items-center justify-between">
            <span className="font-display text-lg text-tui-active tracking-widest uppercase">
              // INTERVIEW
            </span>
            <button
              onClick={finalize}
              disabled={finalizing || pending || (messages ?? []).length === 0}
              className="border border-tui-active/60 text-tui-active px-3 py-1 text-xs font-mono
                         hover:bg-tui-active/10 disabled:opacity-30 tracking-widest uppercase transition-colors"
              title="rebuild the PRD from this interview"
            >
              {finalizing ? "FINALIZING..." : "// FINALIZE → PRD"}
            </button>
          </div>

          <div className="flex-1 min-h-0 overflow-y-auto p-4 space-y-4">
            {!messages ? (
              <div className="text-tui-dim font-mono text-sm tracking-widest animate-flicker">
                LOADING TRANSCRIPT...
              </div>
            ) : messages.length === 0 ? (
              <div className="text-center text-tui-dim py-12">
                <div className="font-display text-2xl tracking-widest">
                  CHANNEL OPEN
                </div>
                <div className="mt-2 text-xs tracking-widest font-mono">
                  describe what you want built — the interviewer refines it into
                  the PRD on the left
                </div>
              </div>
            ) : (
              messages.map((m) =>
                m.role === "user" ? (
                  <div key={m.id} className="flex justify-end">
                    <div className="max-w-[80%] border border-tui-accent/40 bg-tui-accent/5 px-4 py-2">
                      <div className="text-xs text-tui-accent tracking-widest font-mono mb-1">
                        YOU · {fmtTime(m.created_at)}
                      </div>
                      <div className="text-sm text-tui-text whitespace-pre-wrap font-mono">
                        {m.content}
                      </div>
                    </div>
                  </div>
                ) : (
                  <div key={m.id} className="flex justify-start">
                    <div className="max-w-[80%] border border-tui-border bg-tui-bg px-4 py-2">
                      <div className="text-xs text-tui-dim tracking-widest font-mono mb-1">
                        INTERVIEWER · {fmtTime(m.created_at)}
                      </div>
                      <Markdown content={m.content} className="text-sm" />
                    </div>
                  </div>
                )
              )
            )}
            {pending && (
              <div className="flex justify-start">
                <div className="border border-tui-border bg-tui-bg px-4 py-2 text-xs text-tui-accent font-mono tracking-widest animate-flicker">
                  INTERVIEWER PROCESSING...
                  <span className="animate-blink ml-1">▮</span>
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {error && (
            <div className="px-4 py-1 text-xs text-tui-danger font-mono tracking-widest border-t border-tui-border">
              ERR: {error}
            </div>
          )}

          {/* Composer */}
          <div className="border-t border-tui-border p-3 flex gap-2 items-end">
            <textarea
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  send();
                }
              }}
              rows={2}
              placeholder="TRANSMIT TO INTERVIEWER... (enter = send · shift+enter = newline)"
              className="tui-input resize-none flex-1"
              spellCheck={false}
              disabled={pending}
            />
            <button
              onClick={send}
              disabled={pending || !draft.trim()}
              className="border border-tui-accent/60 text-tui-accent px-4 py-2 text-xs font-mono
                         hover:bg-tui-accent/10 disabled:opacity-30 tracking-widest uppercase transition-colors shrink-0"
            >
              {pending ? "..." : "// SEND"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function fmtTime(iso: string) {
  try {
    return new Date(iso).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "";
  }
}
