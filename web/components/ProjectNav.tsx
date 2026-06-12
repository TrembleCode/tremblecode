"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const ITEMS: [string, string][] = [
  ["OVERVIEW", ""],
  ["PRD", "/prd"],
  ["PLAN", "/plan"],
  ["COMMS", "/comms"],
  ["HIL", "/inbox"],
  ["WIKI", "/wiki"],
  ["PREVIEW", "/preview"],
];

export function ProjectNav({ projectId }: { projectId: string }) {
  const pathname = usePathname();
  const base = `/projects/${projectId}`;

  return (
    <nav className="flex flex-wrap gap-2 border-b border-tui-border pb-2 text-xs font-mono tracking-widest uppercase">
      {ITEMS.map(([label, suffix]) => {
        const href = `${base}${suffix}`;
        const active =
          suffix === "" ? pathname === base : pathname.startsWith(href);
        return (
          <Link
            key={href}
            href={href}
            className={
              active
                ? "px-3 py-1 border border-tui-active/60 text-tui-active bg-tui-active/10"
                : "px-3 py-1 border border-tui-border text-tui-dim hover:text-tui-text hover:border-tui-text/40 transition-colors"
            }
          >
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
