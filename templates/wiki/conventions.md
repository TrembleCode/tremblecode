# Wiki conventions (schema)

This `.wiki/` directory is the team's persistent, compounding memory. Agents
write and maintain ALL of it; it is git-versioned with the project. Raw truth
lives in the code — the wiki is the synthesized layer on top: architecture,
decisions, conventions, gotchas.

## Layout

- `index.md` — the catalog. One line per page (`- [Title](pages/...) — hook`),
  grouped by section. ALWAYS read this first; it is the entry point for every
  query. Update it on every ingest.
- `log.md` — append-only chronology. One entry per ingest/lint:
  `## [YYYY-MM-DD] <agent> — <title>` followed by a 1–3 line summary and links.
  Never edit old entries.
- `pages/entities/<name>.md` — one page per significant module/service/
  component: what it is, where it lives, how to work with it.
- `pages/decisions/D-NNN-<slug>.md` — decision records: context, options,
  decision, consequences. Numbered sequentially.
- `pages/concepts/<name>.md` — domain concepts, protocols, data flows.
- `pages/runbooks/<name>.md` — how-to: run tests, seed data, debug X.

## Page format

```markdown
---
title: <Title>
type: entity | decision | concept | runbook
created_by: <agent name>
updated: <YYYY-MM-DD>
links: [<other page paths>]
---

## Summary
2–4 lines anyone can skim.

## Details
The substance. Code paths as `path/to/file.py:symbol`.

## Related
- [Other page](../entities/foo.md)
```

## Operations

- **Ingest** (mandatory after every task, before review/merge): file new
  entities/decisions, update touched pages, update `index.md`, append one
  `log.md` entry. A task that taught you nothing new still gets a log entry.
- **Query**: `index.md` first, then drill into linked pages. Don't grep the
  whole wiki blindly; fix the index instead if you couldn't find something.
- **Lint** (lead, once per milestone): find orphan pages (no inbound links),
  broken links, contradictions between pages, stale claims superseded by newer
  decisions; fix them and log the pass.

## Rules

- Keep pages current: when code changes invalidate a page, update the page in
  the same task.
- Contradictions are bugs: if two pages disagree, the newer decision wins —
  update the older page and link the decision.
- Write for an agent with zero conversation history: no "as discussed",
  no relative dates.
