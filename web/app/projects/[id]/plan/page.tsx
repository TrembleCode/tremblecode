"use client";

import { use, useState } from "react";
import useSWR from "swr";
import { api, fetcher, ApiError } from "@/lib/api";
import type { Plan, ProjectAgent, ProjectDetail } from "@/lib/types";
import { ProjectHeader } from "@/components/ProjectHeader";
import { MarkdownSection } from "@/components/plan/MarkdownSection";
import { StoriesTable } from "@/components/plan/StoriesTable";
import { TasksTable } from "@/components/plan/TasksTable";
import { TasksBoard } from "@/components/plan/TasksBoard";
import { GanttView } from "@/components/plan/GanttView";
import { McpTab } from "@/components/plan/McpTab";

const TABS = ["SPECS", "STORIES", "TASKS", "GANTT", "MCP", "RISKS"] as const;
type Tab = (typeof TABS)[number];

const PLAN_STATUS_STYLE: Record<Plan["status"], string> = {
  draft: "text-tui-accent border-tui-accent/40",
  approved: "text-tui-active border-tui-active/60",
  rejected: "text-tui-danger border-tui-danger/60",
};

export default function PlanPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const { data: project, mutate: mutateProject } = useSWR<ProjectDetail>(
    `/api/projects/${id}`,
    fetcher
  );
  const {
    data: plan,
    error: planError,
    mutate: mutatePlan,
  } = useSWR<Plan>(`/api/projects/${id}/plan`, fetcher, {
    shouldRetryOnError: false,
  });
  const { data: agents } = useSWR<ProjectAgent[]>(
    `/api/projects/${id}/agents`,
    fetcher
  );

  const [tab, setTab] = useState<Tab>("SPECS");
  const [tasksView, setTasksView] = useState<"LIST" | "BOARD">("LIST");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirmApprove, setConfirmApprove] = useState(false);
  const [rejecting, setRejecting] = useState(false);
  const [rejectComments, setRejectComments] = useState("");

  const noPlan = planError instanceof ApiError && planError.status === 404;
  const loading = !plan && !planError;

  async function run(fn: () => Promise<unknown>, label: string) {
    setBusy(true);
    setError(null);
    try {
      await fn();
      mutatePlan();
      mutateProject();
    } catch (e) {
      setError(e instanceof Error ? e.message : `${label} failed`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6 pb-24">
      <ProjectHeader projectId={id} section="PLAN REVIEW" />

      {loading ? (
        <div className="text-tui-dim font-mono text-sm tracking-widest animate-flicker">
          LOADING PLAN...
        </div>
      ) : noPlan || !plan ? (
        <NoPlanState
          project={project}
          busy={busy}
          error={error}
          onStart={() =>
            run(() => api.post(`/api/projects/${id}/start`), "start")
          }
          onGenerate={() =>
            run(() => api.post(`/api/projects/${id}/plan/generate`), "generate")
          }
        />
      ) : (
        <>
          {/* Plan meta + tab bar */}
          <div className="flex items-center gap-3">
            <span className="text-xs text-tui-dim font-mono tracking-widest">
              PLAN v{plan.version}
            </span>
            <span
              className={`px-2 py-0.5 text-xs font-mono border tracking-widest ${PLAN_STATUS_STYLE[plan.status]}`}
            >
              [{plan.status.toUpperCase()}]
            </span>
            {project?.status === "PLANNING" && (
              <span className="text-xs text-tui-accent font-mono tracking-widest animate-flicker">
                THE TEAM LEAD IS PLANNING...
              </span>
            )}
          </div>

          <div className="flex flex-wrap gap-1 border-b border-tui-border">
            {TABS.map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`px-4 py-2 text-xs font-mono tracking-widest uppercase border-b-2 -mb-px transition-colors ${
                  tab === t
                    ? "border-tui-active text-tui-active"
                    : "border-transparent text-tui-dim hover:text-tui-text"
                }`}
              >
                {t}
                {t === "STORIES" && ` [${plan.user_stories.length}]`}
                {t === "TASKS" && ` [${plan.tasks.length}]`}
              </button>
            ))}
          </div>

          {error && (
            <div className="text-xs text-tui-danger font-mono tracking-widest">
              ERR: {error}
            </div>
          )}

          {tab === "SPECS" && (
            <MarkdownSection
              planId={plan.id}
              field="specs_md"
              content={plan.specs_md}
              editable={plan.status === "draft"}
              onSaved={() => mutatePlan()}
            />
          )}
          {tab === "STORIES" && <StoriesTable stories={plan.user_stories} />}
          {tab === "TASKS" && (
            <div className="space-y-3">
              <div className="flex items-center gap-1 text-xs font-mono">
                <span className="text-tui-dim tracking-widest mr-1">VIEW:</span>
                {(["LIST", "BOARD"] as const).map((v) => (
                  <button
                    key={v}
                    onClick={() => setTasksView(v)}
                    className={`px-3 py-1 border tracking-widest uppercase transition-colors ${
                      tasksView === v
                        ? "border-tui-active/60 text-tui-active bg-tui-active/10"
                        : "border-tui-border text-tui-dim hover:text-tui-text hover:border-tui-text/40"
                    }`}
                  >
                    {v}
                  </button>
                ))}
              </div>
              {tasksView === "LIST" ? (
                <TasksTable
                  tasks={plan.tasks}
                  milestones={plan.milestones}
                  editable={plan.status === "draft"}
                  onSaved={() => mutatePlan()}
                />
              ) : (
                <TasksBoard
                  tasks={plan.tasks}
                  milestones={plan.milestones}
                  agents={agents ?? []}
                />
              )}
            </div>
          )}
          {tab === "GANTT" && (
            <GanttView tasks={plan.tasks} milestones={plan.milestones} />
          )}
          {tab === "MCP" && <McpTab projectId={id} />}
          {tab === "RISKS" && (
            <MarkdownSection
              planId={plan.id}
              field="risks_md"
              content={plan.risks_md}
              editable={plan.status === "draft"}
              onSaved={() => mutatePlan()}
            />
          )}

          {/* Sticky review footer */}
          {plan.status === "draft" && (
            <div className="fixed bottom-0 left-64 right-0 z-40 border-t border-tui-border bg-tui-panel px-6 py-3">
              {rejecting ? (
                <div className="flex items-start gap-3">
                  <textarea
                    value={rejectComments}
                    onChange={(e) => setRejectComments(e.target.value)}
                    rows={2}
                    placeholder="REJECTION COMMENTS FOR THE TEAM LEAD..."
                    className="tui-input resize-none flex-1"
                    spellCheck={false}
                    autoFocus
                  />
                  <button
                    onClick={() =>
                      run(async () => {
                        await api.post(`/api/plans/${plan.id}/reject`, {
                          comments: rejectComments,
                        });
                        setRejecting(false);
                        setRejectComments("");
                      }, "reject")
                    }
                    disabled={busy || !rejectComments.trim()}
                    className="border border-tui-danger/60 text-tui-danger px-4 py-2 text-xs font-mono
                               hover:bg-tui-danger/10 disabled:opacity-30 tracking-widest uppercase"
                  >
                    {busy ? "SENDING..." : "// CONFIRM REJECT"}
                  </button>
                  <button
                    onClick={() => setRejecting(false)}
                    className="border border-tui-border px-4 py-2 text-xs text-tui-dim font-mono
                               hover:text-tui-text tracking-widest uppercase"
                  >
                    // ABORT
                  </button>
                </div>
              ) : confirmApprove ? (
                <div className="flex items-center gap-4">
                  <span className="text-xs text-tui-accent font-mono tracking-widest animate-flicker">
                    ⚠ APPROVING UNLEASHES THE TEAM — CONFIRM?
                  </span>
                  <button
                    onClick={() =>
                      run(async () => {
                        await api.post(`/api/plans/${plan.id}/approve`);
                        setConfirmApprove(false);
                      }, "approve")
                    }
                    disabled={busy}
                    className="border border-tui-active/60 text-tui-active px-4 py-2 text-xs font-mono
                               hover:bg-tui-active/10 disabled:opacity-30 tracking-widest uppercase"
                  >
                    {busy ? "APPROVING..." : "// YES, APPROVE"}
                  </button>
                  <button
                    onClick={() => setConfirmApprove(false)}
                    className="border border-tui-border px-4 py-2 text-xs text-tui-dim font-mono
                               hover:text-tui-text tracking-widest uppercase"
                  >
                    // NO
                  </button>
                </div>
              ) : (
                <div className="flex items-center gap-3">
                  <span className="text-xs text-tui-dim font-mono tracking-widest">
                    PLAN v{plan.version} AWAITING REVIEW
                  </span>
                  <div className="ml-auto flex gap-3">
                    <button
                      onClick={() => setRejecting(true)}
                      className="border border-tui-danger/40 text-tui-danger px-4 py-2 text-xs font-mono
                                 hover:bg-tui-danger/10 tracking-widest uppercase"
                    >
                      // REJECT
                    </button>
                    <button
                      onClick={() => setConfirmApprove(true)}
                      className="border border-tui-active/60 text-tui-active px-4 py-2 text-xs font-mono
                                 hover:bg-tui-active/10 tracking-widest uppercase"
                    >
                      // APPROVE PLAN
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}

function NoPlanState({
  project,
  busy,
  error,
  onStart,
  onGenerate,
}: {
  project: ProjectDetail | undefined;
  busy: boolean;
  error: string | null;
  onStart: () => void;
  onGenerate: () => void;
}) {
  const planning = project?.status === "PLANNING";
  return (
    <div className="border border-tui-border bg-tui-panel p-12 text-center">
      <div className="font-display text-3xl text-tui-dim tracking-widest">
        NO PLAN ON FILE
      </div>
      <div className="mt-2 text-xs text-tui-dim tracking-widest font-mono">
        ┌──────────────────────────────────┐
        <br />
        │ the lead drafts specs, stories, │
        <br />
        │ tasks and milestones for review │
        <br />
        └──────────────────────────────────┘
      </div>
      {error && (
        <div className="mt-4 text-xs text-tui-danger font-mono tracking-widest">
          ERR: {error}
        </div>
      )}
      <div className="mt-6">
        {planning ? (
          <div className="text-sm text-tui-accent font-mono tracking-widest animate-flicker">
            THE TEAM LEAD IS PLANNING...
            <span className="animate-blink ml-1">▮</span>
          </div>
        ) : project?.status === "DRAFT" ? (
          <button
            onClick={onStart}
            disabled={busy}
            className="border border-tui-active/60 text-tui-active px-6 py-3 text-sm font-mono
                       hover:bg-tui-active/10 disabled:opacity-30 tracking-widest uppercase"
          >
            {busy ? "STARTING..." : "// START PROJECT"}
          </button>
        ) : (
          <button
            onClick={onGenerate}
            disabled={busy || !project}
            className="border border-tui-accent/60 text-tui-accent px-6 py-3 text-sm font-mono
                       hover:bg-tui-accent/10 disabled:opacity-30 tracking-widest uppercase"
          >
            {busy ? "DISPATCHING..." : "// GENERATE PLAN"}
          </button>
        )}
      </div>
    </div>
  );
}
