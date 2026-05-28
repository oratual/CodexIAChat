# CodexIAChat Documentation Index

## Source Specification

- `docs/specs/agentbus/AGENTBUS_CODEX_MAC_WINDOWS_LINUX.md`

This document is the imported project creation specification. It defines the AgentBus objective, architecture, contracts, workers, deployment phases, tests, security rules, and acceptance criteria.

## Project Control Documents

- `docs/current_state.md`
- `docs/current_decisions.md`
- `docs/current_architecture.md`
- `docs/open_questions.md`
- `docs/api/current_contracts.md`
- `docs/security_model.md`
- `docs/publication_checklist.md`

## MVP Python Operational Docs

- `docs/mvp_python_quickstart.md`
- `docs/mvp_python_configuration.md`
- `docs/nats_private_setup.md`
- `docs/worker_server_usage.md`
- `docs/security_limits.md`
- `docs/runtime_scope_rationale.md`
- `schemas/task.schema.json`
- `schemas/result.schema.json`

## Reading Order

1. Read `docs/current_state.md` to understand what exists now.
2. Read `docs/current_decisions.md` before making architecture or implementation changes.
3. Read `docs/current_architecture.md` before creating services, workers, storage, or deployment scripts.
4. Read `docs/api/current_contracts.md` before changing task, result, or event formats.
5. Read `docs/security_model.md` before implementing NATS, workers, Codex CLI execution, HTTP APIs, MCP tools, logs, artifacts, or locks.
6. Read `docs/open_questions.md` before committing to implementation details.
7. Read `docs/publication_checklist.md` before pushing public changes.
8. Read the MVP Python operational docs before implementing local server, worker, or NATS flows.
9. Use `docs/specs/agentbus/AGENTBUS_CODEX_MAC_WINDOWS_LINUX.md` as the detailed source document.
