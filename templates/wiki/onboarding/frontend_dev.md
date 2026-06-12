---
title: Frontend Developer onboarding
type: runbook
created_by: tremblecode
updated: PROVISIONED
links: [../conventions.md]
---

## Before your first task

1. Read `.wiki/conventions.md` (wiki schema and the mandatory ingest).
2. From `.wiki/index.md`, open the design-language / component-convention
   pages and every decision page touching UI or API contracts.
3. Check the port table (`get_project_info`) before starting any dev server;
   register yours with `register_service`.

## Where you record what

- Design language, component patterns, theming → concept pages
  (`pages/concepts/<name>.md`) so every later UI task matches.
- API contracts you agreed with backend devs → decision pages; never leave a
  contract only in a message thread.
- Every task: update `index.md`, append one `log.md` entry.

## Remember

- Your context is cleared at every task boundary. Anything not in git, the
  wiki, or the task record is lost.
- Coordinate contracts by message BEFORE building against missing endpoints,
  then record the outcome in the wiki.
