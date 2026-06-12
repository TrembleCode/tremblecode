"use client";

import { Fragment, useState } from "react";
import type { UserStory } from "@/lib/types";
import { Markdown } from "@/components/Markdown";

export function StoriesTable({ stories }: { stories: UserStory[] }) {
  const [open, setOpen] = useState<string | null>(null);

  if (stories.length === 0) {
    return (
      <div className="border border-tui-border bg-tui-panel p-8 text-center text-tui-dim text-xs tracking-widest font-mono">
        NO USER STORIES IN THIS PLAN
      </div>
    );
  }

  return (
    <div className="border border-tui-border bg-tui-panel overflow-x-auto">
      <table className="w-full text-sm font-mono">
        <thead>
          <tr className="text-xs text-tui-dim tracking-widest uppercase border-b border-tui-border">
            <th className="text-left px-3 py-2">KEY</th>
            <th className="text-left px-3 py-2">AS A</th>
            <th className="text-left px-3 py-2">I WANT TO</th>
            <th className="text-left px-3 py-2">SO THAT</th>
            <th className="px-3 py-2 w-10" />
          </tr>
        </thead>
        <tbody>
          {stories.map((s) => (
            <Fragment key={s.id}>
              <tr
                className="border-b border-tui-border/40 hover:bg-tui-border/20 cursor-pointer"
                onClick={() => setOpen(open === s.id ? null : s.id)}
              >
                <td className="px-3 py-2 text-tui-accent whitespace-nowrap">
                  {s.story_key}
                </td>
                <td className="px-3 py-2 text-tui-dim">{s.role}</td>
                <td className="px-3 py-2 text-tui-text">{s.action}</td>
                <td className="px-3 py-2 text-tui-dim">{s.benefit}</td>
                <td className="px-3 py-2 text-tui-dim text-center">
                  {open === s.id ? "▾" : "▸"}
                </td>
              </tr>
              {open === s.id && (
                <tr className="border-b border-tui-border/40">
                  <td colSpan={5} className="px-6 py-3 bg-tui-bg">
                    <div className="text-xs text-tui-dim tracking-widest uppercase mb-2">
                      ── ACCEPTANCE CRITERIA ──
                    </div>
                    <Markdown content={s.acceptance_md} className="text-sm" />
                  </td>
                </tr>
              )}
            </Fragment>
          ))}
        </tbody>
      </table>
    </div>
  );
}
