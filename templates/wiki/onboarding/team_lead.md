---
title: Team Lead onboarding
type: runbook
created_by: tremblecode
updated: PROVISIONED
links: [../conventions.md]
---

## First session checklist

1. Read `.wiki/conventions.md` — you own this wiki's health.
2. Read `PRD.md` end to end before planning anything.
3. Skim `.wiki/index.md` and every decision page: past decisions bind you
   unless you supersede them with a new decision page.
4. Check `get_team` for the live roster and `list_tasks` for current state.

## Where you record what

- Plan-level choices (stack, architecture, milestone cuts) → decision pages
  (`pages/decisions/D-NNN-<slug>.md`), linked from `index.md`.
- Merge gotchas and smoke-check procedure → runbook pages.
- Once per milestone: run the wiki lint (orphans, broken links,
  contradictions, stale index entries) and log the pass in `log.md`.

## Remember

- After plan approval your context is cleared and your effort drops to
  medium — the plan, not your memory, is the source of truth from then on.
- Assign tasks with `assign_task` only; the server delivers the brief.
