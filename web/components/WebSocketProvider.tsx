"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import { useSWRConfig } from "swr";
import { WS_BASE } from "@/lib/api";

export interface AfEvent {
  event: string;
  project_id?: string;
  data?: Record<string, unknown>;
}

type Listener = (ev: AfEvent) => void;

interface WsContextValue {
  connected: boolean;
  subscribe: (listener: Listener) => () => void;
}

const WsContext = createContext<WsContextValue>({
  connected: false,
  subscribe: () => () => {},
});

export function useAfSocket() {
  return useContext(WsContext);
}

/** Subscribe to events, optionally filtered to one project. */
export function useAfEvents(listener: Listener, projectId?: string) {
  const { subscribe } = useAfSocket();
  const ref = useRef(listener);
  ref.current = listener;
  useEffect(
    () =>
      subscribe((ev) => {
        if (projectId && ev.project_id !== projectId) return;
        ref.current(ev);
      }),
    [subscribe, projectId]
  );
}

// SWR keys to revalidate per event prefix
const REVALIDATE: Record<string, (ev: AfEvent) => string[]> = {
  project: (ev) => ["/api/projects", `/api/projects/${ev.project_id}`],
  plan: (ev) => [`/api/projects/${ev.project_id}/plan`],
  task: (ev) => [`/api/projects/${ev.project_id}/tasks`],
  agent: (ev) => [`/api/projects/${ev.project_id}/agents`],
  message: (ev) => [`/api/projects/${ev.project_id}/messages`],
  escalation: (ev) => [
    `/api/projects/${ev.project_id}/escalations`,
    "/api/inbox",
  ],
  mcp: (ev) => [`/api/projects/${ev.project_id}/mcp-suggestions`],
  cost: (ev) => [`/api/projects/${ev.project_id}/costs`],
  service: (ev) => [`/api/projects/${ev.project_id}/services`],
};

export function WebSocketProvider({ children }: { children: React.ReactNode }) {
  const [connected, setConnected] = useState(false);
  const listeners = useRef<Set<Listener>>(new Set());
  const { mutate } = useSWRConfig();
  const mutateRef = useRef(mutate);
  mutateRef.current = mutate;

  const subscribe = useCallback((listener: Listener) => {
    listeners.current.add(listener);
    return () => listeners.current.delete(listener);
  }, []);

  useEffect(() => {
    let ws: WebSocket | null = null;
    let retry = 1000;
    let closed = false;
    let timer: ReturnType<typeof setTimeout>;

    function connect() {
      ws = new WebSocket(`${WS_BASE}/ws`);
      ws.onopen = () => {
        retry = 1000;
        setConnected(true);
      };
      ws.onclose = () => {
        setConnected(false);
        if (!closed) {
          timer = setTimeout(connect, retry);
          retry = Math.min(retry * 2, 30000);
        }
      };
      ws.onmessage = (msg) => {
        let ev: AfEvent;
        try {
          ev = JSON.parse(msg.data);
        } catch {
          return;
        }
        const prefix = ev.event.split(".")[0];
        REVALIDATE[prefix]?.(ev).forEach((key) => mutateRef.current(key));
        listeners.current.forEach((l) => l(ev));
      };
    }

    connect();
    return () => {
      closed = true;
      clearTimeout(timer);
      ws?.close();
    };
  }, []);

  return (
    <WsContext.Provider value={{ connected, subscribe }}>
      {children}
    </WsContext.Provider>
  );
}
