import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";
import { WebSocketProvider } from "@/components/WebSocketProvider";
import ThemeToggle from "@/components/ThemeToggle";

export const metadata: Metadata = {
  title: "TrembleCode // COMMAND INTERFACE",
  description: "Autonomous multi-agent software team",
};

function Sidebar() {
  return (
    <aside className="w-72 shrink-0 border-r border-tui-border bg-tui-panel flex flex-col font-mono">
      <div className="p-4 border-b border-tui-border">
        <div className="font-display text-3xl font-bold tracking-tight">
          <span className="text-tui-text">TREMBLE</span>
          <span className="text-tui-accent">CODE</span>
        </div>
        <div className="text-xs text-tui-dim mt-0.5 tracking-widest">
          // COMMAND INTERFACE v2.0
        </div>
      </div>

      <div className="px-4 pt-4 pb-1 text-xs text-tui-border tracking-widest">
        ── NAVIGATION ──
      </div>

      <nav className="flex-1 px-3 space-y-0.5 pb-4">
        <NavLink href="/" prefix="[01]">
          Projects
        </NavLink>
        <NavLink href="/inbox" prefix="[02]">
          Inbox
        </NavLink>
        <NavLink href="/settings" prefix="[03]">
          Settings
        </NavLink>
      </nav>

      <ThemeToggle />

      <div className="p-3 border-t border-tui-border text-xs text-tui-dim flex items-center gap-1">
        <span className="animate-flicker tracking-widest">SYS.READY</span>
        <span className="animate-blink text-tui-active ml-1">▮</span>
      </div>
    </aside>
  );
}

function NavLink({
  href,
  children,
  prefix,
}: {
  href: string;
  children: React.ReactNode;
  prefix: string;
}) {
  return (
    <Link
      href={href}
      className="flex items-center gap-2 px-3 py-2 text-sm text-tui-dim
                 hover:text-tui-text hover:bg-tui-border/30 transition-colors
                 uppercase tracking-widest group"
    >
      <span className="text-tui-border group-hover:text-tui-accent transition-colors text-xs">
        {prefix}
      </span>
      {children}
    </Link>
  );
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){try{var v=['light','dark','crt-dark','crt-light'];var t=localStorage.getItem('tui-theme');document.documentElement.setAttribute('data-theme',v.indexOf(t)>=0?t:'light');}catch(e){}})();`,
          }}
        />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          rel="preconnect"
          href="https://fonts.gstatic.com"
          crossOrigin="anonymous"
        />
        <link
          href="https://fonts.googleapis.com/css2?family=VT323&family=Share+Tech+Mono&family=JetBrains+Mono:wght@400;500;600;700&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        <WebSocketProvider>
          <div className="flex h-screen overflow-hidden bg-tui-bg">
            <Sidebar />
            <main className="flex-1 overflow-y-auto p-6 bg-tui-bg">
              {children}
            </main>
          </div>
        </WebSocketProvider>
      </body>
    </html>
  );
}
