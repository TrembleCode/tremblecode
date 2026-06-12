# Contributing to TrembleCode

Thanks for your interest in TrembleCode. Bug reports, fixes, docs, and feature
work are all welcome.

## Our promise

TrembleCode's core is **AGPL-3.0 and free to self-host, forever** — individuals
and single teams will never hit a paywall. Development is funded by a future
managed cloud and enterprise support (SSO, multi-user, SLAs), not by gating the
features in this repository. See [the README](README.md#sustainability) for the
full story.

## Developer Certificate of Origin & CLA

To keep the project sustainable we maintain a commercial offering alongside the
AGPL core. So that we can offer the same code under both licenses, we ask every
contributor to sign a **[Contributor License Agreement](CLA.md)** the first time
they open a pull request. It's a one-time, one-click signature handled
automatically by [CLA Assistant](https://cla-assistant.io/) — the bot will
comment on your PR with a link.

The CLA does **not** take away your rights: you keep copyright in your
contribution and grant us a license to use it (including under our commercial
license). This is the standard mechanism that lets open-core projects fund
full-time maintenance without ever closing the core. If you have concerns about
it, open a discussion — we're happy to talk it through.

## Development setup

Prerequisites: Docker Desktop, Node 22 + pnpm, Python 3.12 + [uv](https://docs.astral.sh/uv/).

```bash
docker compose up -d redis      # infra
make image                      # build the sandbox image (once)

cd server && uv sync && cd ..
cd web && pnpm install && cd ..

make dev                        # server :8400 + web :3000
```

## Running tests

```bash
make test                       # server suite (workflow, provisioning, costs, mcp, wiki)
cd web && pnpm build            # frontend build must pass
```

Please make sure both pass before opening a PR.

## Pull request conventions

- Branch off `main`; keep PRs focused on one logical change.
- Write a clear description of *what* and *why*; link any related issue.
- Add or update tests for behavior changes.
- Match the surrounding code style — no large unrelated reformatting.
- Don't commit secrets, `.env` files, databases (`*.db*`), or build artifacts.

## Reporting bugs / proposing features

Use the issue templates. For anything security-sensitive, **do not open a public
issue** — follow [SECURITY.md](SECURITY.md) instead.

## Code of Conduct

By participating you agree to abide by our
[Code of Conduct](CODE_OF_CONDUCT.md).
