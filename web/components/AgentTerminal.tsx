"use client";

import { useEffect, useRef, useState } from "react";
import { WS_BASE } from "@/lib/api";
import "@xterm/xterm/css/xterm.css";

type Mode = "ro" | "rw";

/**
 * xterm.js terminal attached to /ws/terminal/{agentId}?mode=ro|rw.
 * xterm is loaded via dynamic import inside useEffect — never on the server.
 */
export function AgentTerminal({ agentId, mode }: { agentId: string; mode: Mode }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [status, setStatus] = useState<"connecting" | "online" | "offline">(
    "connecting"
  );

  useEffect(() => {
    let disposed = false;
    let ws: WebSocket | null = null;
    let retryTimer: ReturnType<typeof setTimeout> | undefined;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    let term: any = null;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    let fit: any = null;

    function sendResize() {
      if (term && ws && ws.readyState === WebSocket.OPEN) {
        ws.send(
          JSON.stringify({ type: "resize", cols: term.cols, rows: term.rows })
        );
      }
    }

    function connect() {
      if (disposed) return;
      setStatus("connecting");
      ws = new WebSocket(`${WS_BASE}/ws/terminal/${agentId}?mode=${mode}`);
      ws.binaryType = "arraybuffer";
      ws.onopen = () => {
        setStatus("online");
        sendResize();
      };
      ws.onmessage = (ev) => {
        if (!term) return;
        if (ev.data instanceof ArrayBuffer) {
          term.write(new Uint8Array(ev.data));
        } else {
          term.write(ev.data);
        }
      };
      ws.onclose = () => {
        if (!disposed) {
          setStatus("offline");
          retryTimer = setTimeout(connect, 3000);
        }
      };
    }

    function onWindowResize() {
      if (fit) {
        fit.fit();
        sendResize();
      }
    }

    (async () => {
      const [{ Terminal }, { FitAddon }] = await Promise.all([
        import("@xterm/xterm"),
        import("@xterm/addon-fit"),
      ]);
      if (disposed || !containerRef.current) return;

      term = new Terminal({
        cursorBlink: true,
        fontFamily: '"Share Tech Mono", monospace',
        fontSize: 13,
        scrollback: 5000,
        theme: {
          background: "#060a06",
          foreground: "#33ff57",
          cursor: "#00ff41",
          selectionBackground: "#1a6626",
        },
        disableStdin: mode === "ro",
      });
      fit = new FitAddon();
      term.loadAddon(fit);
      term.open(containerRef.current);
      fit.fit();

      if (mode === "rw") {
        term.onData((data: string) => {
          if (ws && ws.readyState === WebSocket.OPEN) ws.send(data);
        });
      }

      window.addEventListener("resize", onWindowResize);
      connect();
    })();

    return () => {
      disposed = true;
      clearTimeout(retryTimer);
      window.removeEventListener("resize", onWindowResize);
      ws?.close();
      term?.dispose();
    };
  }, [agentId, mode]);

  return (
    <div className="relative h-full">
      <div ref={containerRef} className="h-full w-full bg-[#060a06]" />
      {status !== "online" && (
        <div className="absolute top-2 right-3 text-xs font-mono tracking-widest text-tui-danger animate-flicker">
          {status === "connecting" ? "LINKING..." : "LINK DOWN — RETRYING"}
        </div>
      )}
    </div>
  );
}
