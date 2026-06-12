# Roadmap

This is a living document — directional, not a commitment. Have an opinion?
Open a [discussion](https://github.com/tremblecode/tremblecode/discussions).

## Now — launch readiness

- [ ] One-command install (`docker compose up`) to replace the multi-step setup
- [ ] Single-admin authentication for the dashboard/API (so it's safe to expose
      beyond localhost)
- [ ] Postgres documented and tested as a first-class database (alongside SQLite)
- [ ] Demo video + quickstart docs
- [ ] CI green on every PR (server tests, web build, secret scan)

## Next — reliability & community

- [ ] Broader test coverage and orchestration reliability hardening
- [ ] Project/stack templates library (community-contributable)
- [ ] Opt-in anonymous usage telemetry (so we know what to prioritize)
- [ ] Better observability: structured logs and run timelines
- [ ] Docs site with architecture deep-dives and troubleshooting

## Later

As the orchestration substrate matures (including Anthropic's native Agent
Teams), we intend to keep TrembleCode's engine swappable and concentrate on the
SDLC layer above it: planning, review, multi-project management, and the
dashboard.

Organizational and managed-hosting features (multi-user, SSO, audit, a hosted
cloud) will fund the project without gating the self-hosted core — see the
[sustainability note](../README.md#sustainability). There's nothing to buy today.
