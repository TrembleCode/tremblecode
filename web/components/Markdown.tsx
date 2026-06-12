"use client";

import { useMemo } from "react";
import { marked } from "marked";

export function Markdown({
  content,
  className,
}: {
  content: string;
  className?: string;
}) {
  const html = useMemo(() => marked(content || "") as string, [content]);
  if (!content) {
    return (
      <p className="text-tui-border font-mono text-xs tracking-widest">
        NO CONTENT<span className="animate-blink ml-1">▮</span>
      </p>
    );
  }
  return (
    <div
      className={`tui-prose ${className ?? ""}`}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
