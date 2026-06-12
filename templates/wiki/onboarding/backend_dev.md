---
title: Backend Developer onboarding
type: runbook
created_by: tremblecode
updated: PROVISIONED
links: [../conventions.md]
---

## Before your first task

1. Read `.wiki/conventions.md` (wiki schema and the mandatory ingest).
2. From `.wiki/index.md`, open every entity page for server-side modules and
   every decision page touching APIs, schemas, or data models.
3. Find the test runbook (how to run the suite) — if it doesn't exist yet,
   create it as your first ingest.

## Where you record what

- New module/service → entity page (`pages/entities/<name>.md`).
- Non-obvious technical choice (library, schema shape, protocol) → decision
  page. If the brief forced the choice, still record why.
- Every task: update `index.md`, append one `log.md` entry — even when you
  learned nothing new.

## Remember

- Your context is cleared at every task boundary. Anything not in git, the
  wiki, or the task record is lost.
- `request_review` warns when your branch has no `.wiki/` changes — do the
  ingest before requesting, not after.
