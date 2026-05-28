# Current State

Project name: `CodexIAChat`

Date: 2026-05-28

## What Exists

- The AgentBus project specification has been imported into `docs/specs/agentbus/AGENTBUS_CODEX_MAC_WINDOWS_LINUX.md`.
- Documentation entrypoints have been created under `docs/`.
- MVP Python runtime has been added under `src/codexiachat/agentbus/`.
- MVP Python operational documentation has been added for quickstart, configuration, private NATS, worker/server usage, and security limits.
- JSON schemas have been added under `schemas/`.
- Security/e2e tests have been added under `tests/`.
- Runtime scope rationale has been documented in `docs/runtime_scope_rationale.md`.
- The project has open-source repository hygiene files for security, contribution, conduct, support, licensing, and release checks.
- The project is published on GitHub as `CodexIAChat`.

## What Does Not Exist Yet

- No NATS runtime adapter is implemented yet. The MVP uses HTTP for admission and worker `run-once`; NATS remains the planned private wake-up transport.
- No OS service installers are implemented yet.
- No database schema or migrations exist in this repository.
- No dashboard or MCP server exists in this repository.
- No secrets or deployment configuration exist in this repository.
- No deployment stack is implemented in this repository.

## Warning

The Python MVP is local/private only. It must not be deployed as shared infrastructure until NATS/private networking, OS users, service installation, and deployment ownership are explicitly decided.
