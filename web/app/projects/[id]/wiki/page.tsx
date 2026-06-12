"use client";

import { use, useMemo, useState } from "react";
import useSWR from "swr";
import { marked } from "marked";
import { fetcher } from "@/lib/api";
import type { WikiNode, WikiTree } from "@/lib/types";
import { ProjectHeader } from "@/components/ProjectHeader";

export default function WikiPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const { data: tree, error: treeError } = useSWR<WikiTree>(
    `/api/projects/${id}/wiki/tree`,
    fetcher,
    { shouldRetryOnError: false }
  );
  const [path, setPath] = useState("index.md");
  const { data: page, error: pageError } = useSWR<{ content: string }>(
    `/api/projects/${id}/wiki/page?path=${encodeURIComponent(path)}`,
    fetcher,
    { shouldRetryOnError: false }
  );

  const html = useMemo(() => {
    if (!page?.content) return "";
    // [[wikilink]] and [[wikilink|label]] → markdown links
    const pre = page.content.replace(
      /\[\[([^\]|]+)(?:\|([^\]]+))?\]\]/g,
      (_m, target: string, label?: string) => {
        const t = target.trim();
        const href = t.endsWith(".md") ? t : `${t}.md`;
        return `[${label?.trim() ?? t}](${href})`;
      }
    );
    return marked(pre) as string;
  }, [page?.content]);

  function handleClick(e: React.MouseEvent<HTMLDivElement>) {
    const anchor = (e.target as HTMLElement).closest("a");
    if (!anchor) return;
    const href = anchor.getAttribute("href") ?? "";
    if (/^(https?:)?\/\//.test(href) || href.startsWith("#")) return;
    if (href.endsWith(".md")) {
      e.preventDefault();
      setPath(resolvePath(path, href));
    }
  }

  const noWiki = !!treeError;

  return (
    <div className="flex flex-col h-full space-y-4">
      <ProjectHeader projectId={id} section="WIKI · TEAM KNOWLEDGE BASE" />

      {!tree && !treeError ? (
        <div className="text-tui-dim font-mono text-sm tracking-widest animate-flicker">
          INDEXING ARCHIVE...
        </div>
      ) : noWiki ? (
        <div className="border border-tui-border bg-tui-panel p-12 text-center text-tui-dim">
          <div className="font-display text-2xl tracking-widest">
            ARCHIVE EMPTY
          </div>
          <div className="mt-2 text-xs tracking-widest font-mono">
            the team has not written any wiki pages yet
          </div>
        </div>
      ) : (
        <div className="flex-1 min-h-0 flex gap-4">
          {/* File tree */}
          <aside className="w-64 shrink-0 border border-tui-border bg-tui-panel overflow-y-auto">
            <div className="px-3 py-2 border-b border-tui-border text-xs text-tui-dim tracking-widest font-mono">
              ── FILES ──
            </div>
            <div className="p-2">
              {(tree?.tree ?? []).length === 0 ? (
                <div className="text-xs text-tui-border font-mono tracking-widest p-2">
                  NO PAGES
                </div>
              ) : (
                (tree?.tree ?? []).map((n) => (
                  <TreeNode
                    key={n.path}
                    node={n}
                    depth={0}
                    selected={path}
                    onSelect={setPath}
                  />
                ))
              )}
            </div>
          </aside>

          {/* Page */}
          <div className="flex-1 min-w-0 border border-tui-border bg-tui-panel overflow-y-auto">
            <div className="px-4 py-2 border-b border-tui-border text-xs text-tui-accent tracking-widest font-mono sticky top-0 bg-tui-panel">
              /{path}
            </div>
            <div className="p-6">
              {pageError ? (
                <div className="text-center text-tui-dim py-12">
                  <div className="font-display text-2xl tracking-widest">
                    PAGE NOT FOUND
                  </div>
                  <div className="mt-2 text-xs tracking-widest font-mono">
                    /{path} does not exist (yet)
                  </div>
                </div>
              ) : !page ? (
                <div className="text-tui-dim font-mono text-sm tracking-widest animate-flicker">
                  DECRYPTING PAGE...
                </div>
              ) : (
                <div
                  className="tui-prose"
                  onClick={handleClick}
                  dangerouslySetInnerHTML={{ __html: html }}
                />
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function TreeNode({
  node,
  depth,
  selected,
  onSelect,
}: {
  node: WikiNode;
  depth: number;
  selected: string;
  onSelect: (path: string) => void;
}) {
  const [open, setOpen] = useState(true);

  if (node.type === "dir") {
    return (
      <div>
        <button
          onClick={() => setOpen(!open)}
          className="w-full text-left px-2 py-1 text-xs font-mono tracking-widest text-tui-dim
                     hover:text-tui-text uppercase"
          style={{ paddingLeft: `${depth * 12 + 8}px` }}
        >
          {open ? "▾" : "▸"} {node.name}/
        </button>
        {open &&
          (node.children ?? []).map((c) => (
            <TreeNode
              key={c.path}
              node={c}
              depth={depth + 1}
              selected={selected}
              onSelect={onSelect}
            />
          ))}
      </div>
    );
  }

  const active = node.path === selected;
  return (
    <button
      onClick={() => onSelect(node.path)}
      className={`w-full text-left px-2 py-1 text-xs font-mono tracking-wide truncate ${
        active
          ? "text-tui-active bg-tui-active/10 border-l-2 border-tui-active"
          : "text-tui-text hover:bg-tui-border/20"
      }`}
      style={{ paddingLeft: `${depth * 12 + 8}px` }}
      title={node.path}
    >
      ▪ {node.name}
    </button>
  );
}

/** Resolve a relative .md href against the current page path. */
function resolvePath(current: string, href: string) {
  if (href.startsWith("/")) return href.slice(1);
  const parts = current.split("/").slice(0, -1);
  for (const seg of href.split("/")) {
    if (seg === "" || seg === ".") continue;
    if (seg === "..") parts.pop();
    else parts.push(seg);
  }
  return parts.join("/");
}
