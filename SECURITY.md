# Security Policy

TrembleCode runs autonomous coding agents with broad permissions inside
containers on your own infrastructure. We take its security posture seriously
and ask you to deploy it with the threat model below in mind.

## Supported versions

TrembleCode is pre-1.0 and moves quickly. Security fixes land on `main` and the
latest release. Please run a recent version before reporting.

## Reporting a vulnerability

**Please do not open a public issue for security problems.**

- Preferred: open a private [GitHub Security Advisory](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)
  on this repository.
- Or email **security@tremblecode.dev**.

We aim to acknowledge reports within 72 hours and to keep you updated as we work
on a fix. We'll credit you (if you wish) once a fix ships.

## Threat model & safe deployment

TrembleCode is designed to be run by an operator on infrastructure they control.
Keep these properties in mind:

- **Agents run with full permissions inside their project container.** Each
  project gets its own sandbox container; project directories are identity-mounted
  (same absolute path inside and out) so git worktrees stay valid. Treat anything
  an agent can reach from inside that container as in-scope for the agent.
- **There is no built-in authentication on the API/dashboard yet.** Do **not**
  expose the server (`:8400`) or dashboard (`:3000`) to the public internet.
  Run them on `localhost`, behind a VPN, or behind your own authenticating
  reverse proxy. A single-admin auth gate is on the near-term roadmap.
- **Destructive and sensitive operations are gated by human escalations.** The
  default escalation policy routes destructive ops, milestone gates, and
  ambiguous decisions to the Inbox for human approval. Keep these defaults
  conservative; loosening them shifts risk onto you.
- **Secrets at rest are encrypted** with a Fernet key (`TC_FERNET_KEY`), and the
  `/internal` endpoints require a shared secret (`TC_INTERNAL_SECRET`). Set both
  to strong values in any non-throwaway deployment.
- **Bring-your-own credentials.** Your Claude login / API key lives in the
  agent home (`~/.tremblecode/agent-home`). Protect that directory as you would
  any credential store.

If you find a way to escape these boundaries (container escape, unauthenticated
access to a deployment intended to be local, secret disclosure, etc.), please
report it via the channels above.
