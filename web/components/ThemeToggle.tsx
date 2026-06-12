"use client";

import { useEffect, useState } from "react";

const THEMES = ["dark", "light", "normal-dark", "normal-light"] as const;
type Theme = (typeof THEMES)[number];

const LABELS: Record<Theme, string> = {
  dark: "CRT.DARK",
  light: "CRT.LITE",
  "normal-dark": "DARK",
  "normal-light": "LITE",
};

const STORAGE_KEY = "tui-theme";

function coerce(value: string | null): Theme {
  return (THEMES as readonly string[]).includes(value ?? "")
    ? (value as Theme)
    : "dark";
}

export default function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>("dark");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const initial = coerce(localStorage.getItem(STORAGE_KEY));
    setTheme(initial);
    document.documentElement.setAttribute("data-theme", initial);
    setMounted(true);
  }, []);

  function cycle() {
    const next = THEMES[(THEMES.indexOf(theme) + 1) % THEMES.length];
    setTheme(next);
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem(STORAGE_KEY, next);
  }

  if (!mounted) {
    return (
      <button
        disabled
        aria-label="Toggle theme"
        className="w-full flex items-center gap-2 px-3 py-2 text-xs uppercase tracking-widest
                   text-tui-border cursor-not-allowed"
      >
        <span className="text-tui-border text-xs">[TH]</span>
        ░░░░░░░░░
      </button>
    );
  }

  return (
    <button
      onClick={cycle}
      aria-label="Cycle theme"
      title="Cycle theme: CRT dark → CRT light → dark → light"
      className="w-full flex items-center gap-2 px-3 py-2 text-xs uppercase tracking-widest
                 text-tui-dim hover:text-tui-text hover:bg-tui-border/30
                 transition-colors group border-t border-tui-border/50"
    >
      <span className="text-tui-border group-hover:text-tui-accent transition-colors text-xs shrink-0">
        [TH]
      </span>
      <span className="relative flex items-center gap-1 font-mono text-xs">
        {THEMES.map((t) => (
          <span
            key={t}
            className={t === theme ? "text-tui-active" : "text-tui-dim"}
          >
            {t === theme ? "█" : "░"}
          </span>
        ))}
        <span className="ml-1 text-tui-dim">{LABELS[theme]}</span>
      </span>
      <span className="ml-auto text-tui-border group-hover:text-tui-accent transition-colors text-xs animate-blink">
        ▮
      </span>
    </button>
  );
}
