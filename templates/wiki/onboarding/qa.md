---
title: QA Engineer onboarding
type: runbook
created_by: tremblecode
updated: PROVISIONED
links: [../conventions.md]
---

## Before your first review

1. Read `.wiki/conventions.md` (wiki schema and operations).
2. From `.wiki/index.md`, open the test runbook (how to run the full suite)
   and any defect-pattern runbooks from earlier reviews.
3. Fetch the task brief with `list_tasks` — the review-request message only
   carries the branch and the developer's notes.

## Where you record what

- Recurring defect patterns (what keeps breaking and how you catch it) →
  runbook pages (`pages/runbooks/<name>.md`).
- Gaps in acceptance criteria you had to interpret → message the lead AND
  note the interpretation in the review record.
- Update `index.md`, append `log.md` — BEFORE `submit_review`: your context
  is cleared right after each delivered review.

## Remember

- Check the branch out DETACHED (`git checkout --detach <branch>`) in YOUR
  worktree — the branch lives in the developer's worktree.
- You never fix code and never merge; report with a concrete, numbered
  checklist.
