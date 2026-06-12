import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        tui: {
          bg:     "rgb(var(--tui-bg-rgb) / <alpha-value>)",
          panel:  "rgb(var(--tui-panel-rgb) / <alpha-value>)",
          border: "rgb(var(--tui-border-rgb) / <alpha-value>)",
          text:   "rgb(var(--tui-text-rgb) / <alpha-value>)",
          dim:    "rgb(var(--tui-dim-rgb) / <alpha-value>)",
          accent: "rgb(var(--tui-accent-rgb) / <alpha-value>)",
          danger: "rgb(var(--tui-danger-rgb) / <alpha-value>)",
          active: "rgb(var(--tui-active-rgb) / <alpha-value>)",
          white:  "#ffffff",
        },
      },
      fontFamily: {
        // resolved per theme in globals.css (CRT: VT323/Share Tech Mono,
        // normal: Source Serif 4/JetBrains Mono)
        display: ["var(--font-display)", "monospace"],
        mono:    ["var(--font-mono)", "monospace"],
      },
      keyframes: {
        blink: {
          "0%, 100%": { opacity: "1" },
          "50%":      { opacity: "0" },
        },
        flicker: {
          "0%, 19%, 21%, 23%, 25%, 54%, 56%, 100%": { opacity: "1" },
          "20%, 22%, 24%, 55%": { opacity: "0.4" },
        },
        glitch: {
          "0%":   { clipPath: "inset(0 0 100% 0)", transform: "translate(0)" },
          "20%":  { clipPath: "inset(10% 0 80% 0)", transform: "translate(-2px, 1px)" },
          "60%":  { clipPath: "inset(60% 0 20% 0)", transform: "translate(2px, -1px)" },
          "100%": { clipPath: "inset(0 0 0 0)",      transform: "translate(0)" },
        },
      },
      animation: {
        blink:   "blink 1s step-end infinite",
        flicker: "flicker 4s linear infinite",
        glitch:  "glitch 0.3s linear",
      },
    },
  },
  plugins: [],
};

export default config;
