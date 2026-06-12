"use client";

import { use, useEffect, useMemo, useRef, useState } from "react";
import useSWR from "swr";
import { api, fetcher } from "@/lib/api";
import type { Message, ProjectAgent } from "@/lib/types";
import { ProjectHeader } from "@/components/ProjectHeader";
import { Markdown } from "@/components/Markdown";

const ACK_GLYPH: Record<Message["status"], { glyph: string; cls: string }> = {
  queued: { glyph: "◌", cls: "text-tui-dim" },
  notified: { glyph: "▸", cls: "text-tui-dim" },
  delivered: { glyph: "✓", cls: "text-tui-text" },
  acked: { glyph: "✓✓", cls: "text-tui-active" },
  expired: { glyph: "✕", cls: "text-tui-danger" },
};

const BROADCAST_KEY = "__broadcast__";
const pairKey = (a: string, b: string) => [a, b].sort().join(" → ");

interface Channel {
  key: string;
  a: string;
  b: string;
  broadcast: boolean;
  msgs: Message[]; // ascending
  last?: Message;
  unread: number;
}

export default function CommsPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const { data: messages, mutate } = useSWR<Message[]>(
    `/api/projects/${id}/messages`,
    fetcher,
    { refreshInterval: 3000 }
  );
  const { data: agents } = useSWR<ProjectAgent[]>(
    `/api/projects/${id}/agents`,
    fetcher,
    { refreshInterval: 3000 }
  );

  const [selected, setSelected] = useState<string | null>(null);
  // human↔agent chats opened from the composer that have no traffic yet
  const [drafts, setDrafts] = useState<{ key: string; a: string; b: string; broadcast: boolean }[]>([]);
  const [showNew, setShowNew] = useState(false);
  const [body, setBody] = useState("");
  const [ackRequested, setAckRequested] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const leadNames = useMemo(
    () => new Set((agents ?? []).filter((a) => a.kind === "lead").map((a) => a.name)),
    [agents]
  );

  // ── derive channels from message traffic ──
  const channels = useMemo<Channel[]>(() => {
    const sorted = [...(messages ?? [])].sort(
      (x, y) =>
        new Date(x.created_at).getTime() - new Date(y.created_at).getTime()
    );
    const map = new Map<string, Channel>();
    for (const m of sorted) {
      let key: string, a: string, b: string, broadcast = false;
      if (m.to_participant === "broadcast") {
        key = BROADCAST_KEY;
        a = "broadcast";
        b = "*";
        broadcast = true;
      } else {
        const pair = [m.from_participant, m.to_participant].sort();
        key = pair.join(" → ");
        a = pair[0];
        b = pair[1];
      }
      const ex = map.get(key);
      if (ex) ex.msgs.push(m);
      else map.set(key, { key, a, b, broadcast, msgs: [m], unread: 0 });
    }
    const out = [...map.values()].map((ch) => ({
      ...ch,
      last: ch.msgs[ch.msgs.length - 1],
      unread: ch.msgs.filter(
        (m) =>
          m.ack_requested && m.status !== "acked" && m.status !== "expired"
      ).length,
    }));
    out.sort(
      (x, y) =>
        new Date(y.last!.created_at).getTime() -
        new Date(x.last!.created_at).getTime()
    );
    return out;
  }, [messages]);

  // merge freshly-started (empty) chats on top of the live ones
  const allChannels = useMemo<Channel[]>(() => {
    const draftChannels: Channel[] = drafts
      .filter((d) => !channels.some((c) => c.key === d.key))
      .map((d) => ({ ...d, msgs: [], unread: 0 }));
    return [...draftChannels, ...channels];
  }, [drafts, channels]);

  const activeChannel = allChannels.find((c) => c.key === selected) ?? null;

  useEffect(() => {
    if (!selected && allChannels.length) setSelected(allChannels[0].key);
  }, [allChannels, selected]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [activeChannel?.msgs.length, selected]);

  // who a human-sent message in this chat is addressed to (null ⇒ read-only)
  const target = useMemo(() => {
    if (!activeChannel) return null;
    if (activeChannel.broadcast) return "broadcast";
    const parts = [activeChannel.a, activeChannel.b];
    if (parts.includes("human")) return parts.find((p) => p !== "human")!;
    return null; // agent↔agent → observe only
  }, [activeChannel]);

  function startChat(name: string) {
    setShowNew(false);
    const key = name === "broadcast" ? BROADCAST_KEY : pairKey("human", name);
    if (!allChannels.some((c) => c.key === key)) {
      setDrafts((d) => [
        {
          key,
          a: name === "broadcast" ? "broadcast" : pairKey("human", name).split(" → ")[0],
          b: name === "broadcast" ? "*" : pairKey("human", name).split(" → ")[1],
          broadcast: name === "broadcast",
        },
        ...d,
      ]);
    }
    setSelected(key);
  }

  function participantClass(name: string) {
    if (name === "broadcast" || name === "*")
      return "text-tui-dim border-tui-border";
    if (name === "human") return "text-tui-accent border-tui-accent/40";
    if (leadNames.has(name)) return "text-tui-accent border-tui-accent/40";
    return "text-tui-text border-tui-border";
  }

  function channelTitle(ch: Channel) {
    if (ch.broadcast) return "BROADCAST NET";
    const parts = [ch.a, ch.b];
    if (parts.includes("human")) return parts.find((p) => p !== "human")!;
    return `${ch.a} ↔ ${ch.b}`;
  }

  async function send() {
    if (!body.trim() || sending || !target) return;
    setSending(true);
    setError(null);
    try {
      await api.post(`/api/projects/${id}/messages`, {
        to: target,
        body_md: body,
        ack_requested: ackRequested,
      });
      setBody("");
      setAckRequested(false);
      mutate();
    } catch (e) {
      setError(e instanceof Error ? e.message : "send failed");
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="flex flex-col h-full space-y-4">
      <ProjectHeader projectId={id} section="COMMS · MESSAGE TRAFFIC" />

      <div className="flex-1 min-h-0 grid grid-cols-[280px_1fr] gap-4">
        {/* ── chat roster ── */}
        <div className="border border-tui-border bg-tui-panel flex flex-col min-h-0 relative">
          <div className="px-3 py-2 border-b border-tui-border text-[10px] font-mono tracking-widest text-tui-dim flex items-center justify-between">
            <span>CHATS</span>
            <button
              onClick={() => setShowNew((s) => !s)}
              className="border border-tui-accent/60 text-tui-accent px-2 py-0.5 tracking-widest
                         hover:bg-tui-accent/10 transition-colors uppercase"
            >
              {showNew ? "× CLOSE" : "+ NEW"}
            </button>
          </div>

          {/* new-chat picker */}
          {showNew && (
            <div className="absolute z-20 top-9 left-2 right-2 border border-tui-accent/40 bg-tui-bg shadow-lg max-h-72 overflow-y-auto">
              <div className="px-3 py-1.5 text-[10px] font-mono tracking-widest text-tui-dim border-b border-tui-border">
                START CHAT WITH
              </div>
              <button
                onClick={() => startChat("broadcast")}
                className="w-full text-left px-3 py-2 text-xs font-mono tracking-widest text-tui-dim
                           hover:bg-tui-accent/10 border-b border-tui-border/50"
              >
                📡 BROADCAST — ALL NET
              </button>
              {(agents ?? []).map((a) => (
                <button
                  key={a.id}
                  onClick={() => startChat(a.name)}
                  className="w-full text-left px-3 py-2 text-xs font-mono tracking-widest
                             hover:bg-tui-accent/10 border-b border-tui-border/50 uppercase
                             flex items-center justify-between"
                >
                  <span className={participantClass(a.name).split(" ")[0]}>
                    {a.name}
                  </span>
                  <span className="text-tui-border lowercase">{a.role_key}</span>
                </button>
              ))}
              {(agents ?? []).length === 0 && (
                <div className="px-3 py-3 text-xs text-tui-border font-mono tracking-widest">
                  NO AGENTS YET
                </div>
              )}
            </div>
          )}

          <div className="flex-1 overflow-y-auto">
            {!messages ? (
              <div className="p-3 text-tui-dim font-mono text-xs tracking-widest animate-flicker">
                SCANNING NET...
              </div>
            ) : allChannels.length === 0 ? (
              <div className="p-4 text-tui-dim font-mono text-xs tracking-widest">
                NO CHATS YET — HIT [+ NEW] TO OPEN ONE
              </div>
            ) : (
              allChannels.map((ch) => (
                <ChannelRow
                  key={ch.key}
                  ch={ch}
                  title={channelTitle(ch)}
                  active={ch.key === selected}
                  onClick={() => setSelected(ch.key)}
                  participantClass={participantClass}
                />
              ))
            )}
          </div>
        </div>

        {/* ── chat reader ── */}
        <div className="border border-tui-border bg-tui-panel flex flex-col min-h-0">
          {activeChannel ? (
            <>
              <div className="px-4 py-2.5 border-b border-tui-border flex items-center gap-2 text-xs font-mono">
                <span className="font-display text-lg text-tui-active tracking-widest uppercase">
                  {channelTitle(activeChannel)}
                </span>
                {!activeChannel.broadcast &&
                  ![activeChannel.a, activeChannel.b].includes("human") && (
                    <span className="border border-tui-border px-1.5 py-0.5 tracking-widest text-tui-dim">
                      OBSERVING
                    </span>
                  )}
                <span className="ml-auto text-tui-dim tracking-widest">
                  {activeChannel.msgs.length} MSG
                </span>
              </div>

              <div className="flex-1 overflow-y-auto p-4 space-y-3">
                {activeChannel.msgs.length === 0 ? (
                  <div className="text-center text-tui-dim py-12 text-xs font-mono tracking-widest">
                    NO MESSAGES YET — SAY SOMETHING BELOW
                  </div>
                ) : (
                  activeChannel.msgs.map((m, i) => {
                    const prev = activeChannel.msgs[i - 1];
                    return (
                      <ChatBubble
                        key={m.id}
                        msg={m}
                        right={m.from_participant === "human"}
                        grouped={
                          !!prev &&
                          prev.from_participant === m.from_participant
                        }
                        broadcast={activeChannel.broadcast}
                        participantClass={participantClass}
                      />
                    );
                  })
                )}
                <div ref={bottomRef} />
              </div>

              {error && (
                <div className="px-4 py-1 text-xs text-tui-danger font-mono tracking-widest border-t border-tui-border">
                  ERR: {error}
                </div>
              )}

              {/* composer — only where the human is a party */}
              {target ? (
                <div className="border-t border-tui-border p-3 flex gap-2 items-end">
                  <textarea
                    value={body}
                    onChange={(e) => setBody(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.shiftKey) {
                        e.preventDefault();
                        send();
                      }
                    }}
                    rows={2}
                    placeholder={`MESSAGE ${target.toUpperCase()}... (markdown · enter = send)`}
                    className="tui-input resize-none flex-1"
                    spellCheck={false}
                  />
                  <div className="flex flex-col items-end gap-1.5 shrink-0">
                    <label className="flex items-center gap-1.5 text-[10px] text-tui-dim tracking-widest font-mono cursor-pointer select-none">
                      <input
                        type="checkbox"
                        checked={ackRequested}
                        onChange={(e) => setAckRequested(e.target.checked)}
                        className="accent-current"
                      />
                      ACK
                    </label>
                    <button
                      onClick={send}
                      disabled={sending || !body.trim()}
                      className="border border-tui-accent/60 text-tui-accent px-4 py-2 text-xs font-mono
                                 hover:bg-tui-accent/10 disabled:opacity-30 tracking-widest uppercase"
                    >
                      {sending ? "..." : "// TRANSMIT"}
                    </button>
                  </div>
                </div>
              ) : (
                <div className="border-t border-tui-border px-4 py-3 text-xs text-tui-dim font-mono tracking-widest">
                  ▸ OBSERVING AGENT-TO-AGENT TRAFFIC — read only
                </div>
              )}
            </>
          ) : (
            <div className="flex-1 flex items-center justify-center text-center text-tui-dim">
              <div>
                <div className="font-display text-2xl tracking-widest">
                  RADIO SILENCE
                </div>
                <div className="mt-2 text-xs tracking-widest font-mono">
                  pick a chat — or hit [+ NEW] to open one
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function ChannelRow({
  ch,
  title,
  active,
  onClick,
  participantClass,
}: {
  ch: Channel;
  title: string;
  active: boolean;
  onClick: () => void;
  participantClass: (n: string) => string;
}) {
  const preview = ch.last?.body_md.replace(/\s+/g, " ").trim();
  const observe =
    !ch.broadcast && ![ch.a, ch.b].includes("human");
  return (
    <button
      onClick={onClick}
      className={`w-full text-left px-3 py-2.5 border-b border-tui-border/50 transition-colors block ${
        active
          ? "bg-tui-active/10 border-l-2 border-l-tui-active"
          : "hover:bg-tui-bg border-l-2 border-l-transparent"
      }`}
    >
      <div className="flex items-center gap-1.5 text-[11px] font-mono tracking-widest">
        <span
          className={`uppercase truncate ${
            ch.broadcast
              ? "text-tui-dim"
              : participantClass(title).split(" ")[0]
          }`}
        >
          {ch.broadcast ? "📡 BROADCAST" : title}
        </span>
        {observe && <span className="text-tui-border">·OBS</span>}
        {ch.unread > 0 && (
          <span className="ml-auto text-tui-accent" title="awaiting ack">
            ●{ch.unread}
          </span>
        )}
      </div>
      <div className="mt-1 text-[11px] text-tui-dim font-mono truncate">
        {ch.last ? (
          <>
            <span className="text-tui-border">{ch.last.from_participant}:</span>{" "}
            {preview || "—"}
          </>
        ) : (
          <span className="text-tui-border">NEW CHANNEL — say hello</span>
        )}
      </div>
      {ch.last && (
        <div className="mt-0.5 text-[10px] text-tui-border font-mono flex items-center gap-2">
          <span>
            {new Date(ch.last.created_at).toLocaleString([], {
              month: "2-digit",
              day: "2-digit",
              hour: "2-digit",
              minute: "2-digit",
            })}
          </span>
          <span className="ml-auto">{ch.msgs.length} MSG</span>
        </div>
      )}
    </button>
  );
}

function ChatBubble({
  msg,
  right,
  grouped,
  broadcast,
  participantClass,
}: {
  msg: Message;
  right: boolean;
  grouped: boolean;
  broadcast: boolean;
  participantClass: (n: string) => string;
}) {
  const [expanded, setExpanded] = useState(false);
  const long = msg.body_md.length > 400;
  const shown = !long || expanded ? msg.body_md : msg.body_md.slice(0, 400);
  const ack = ACK_GLYPH[msg.status] ?? ACK_GLYPH.queued;

  return (
    <div className={`flex flex-col ${right ? "items-end" : "items-start"}`}>
      {!grouped && (
        <div className="flex items-center gap-1.5 mb-1 text-[10px] font-mono tracking-widest">
          <span
            className={`border px-1.5 py-0.5 uppercase ${participantClass(msg.from_participant)}`}
          >
            {msg.from_participant}
          </span>
          {broadcast && (
            <>
              <span className="text-tui-border">→</span>
              <span className="text-tui-dim">ALL NET</span>
            </>
          )}
        </div>
      )}
      <div
        className={`max-w-[80%] border bg-tui-bg p-3 ${
          right ? "border-tui-accent/30" : "border-tui-border"
        }`}
      >
        {msg.subject && (
          <div className="text-sm text-tui-active font-mono font-bold tracking-wide mb-1.5">
            {msg.subject}
          </div>
        )}
        <Markdown content={shown} className="text-sm" />
        {long && (
          <button
            onClick={() => setExpanded(!expanded)}
            className="mt-1 text-xs text-tui-accent font-mono tracking-widest hover:text-tui-text"
          >
            {expanded ? "[− COLLAPSE]" : "[+ EXPAND]"}
          </button>
        )}
        {msg.status === "acked" && msg.ack_note && (
          <div className="mt-2 border-t border-tui-border/40 pt-1.5 text-xs text-tui-active font-mono">
            ✓✓ ACK: {msg.ack_note}
          </div>
        )}
      </div>
      <div className="mt-1 flex items-center gap-2 text-[10px] text-tui-dim font-mono">
        {msg.task_key && <span className="text-tui-accent">{msg.task_key}</span>}
        {msg.priority && msg.priority !== "normal" && (
          <span className="text-tui-danger uppercase tracking-widest">
            !{msg.priority}
          </span>
        )}
        <span>
          {new Date(msg.created_at).toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          })}
        </span>
        <span
          className={ack.cls}
          title={
            msg.status === "acked" && msg.ack_note
              ? `ACK: ${msg.ack_note}`
              : msg.status.toUpperCase()
          }
        >
          {ack.glyph}
        </span>
      </div>
    </div>
  );
}
