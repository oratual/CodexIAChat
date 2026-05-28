# CodexIAChat

[![Security](https://github.com/oratual/CodexIAChat/actions/workflows/security.yml/badge.svg)](https://github.com/oratual/CodexIAChat/actions/workflows/security.yml)

CodexIAChat is an AgentBus-style coordination system for Codex instances on Windows, macOS, and Linux.

The imported source specification is:

- `docs/specs/agentbus/AGENTBUS_CODEX_MAC_WINDOWS_LINUX.md`

Current status: Python MVP runtime is implemented for local/private use. It includes an HTTP admission server, a run-once worker, JSON-backed state, static command profiles, path enforcement, replay protection, log redaction, and security tests. NATS remains documented as the wake-up transport target and is not faked by the MVP runtime.

## Documentation Entrypoints

- `docs/index.md`: documentation map and reading order.
- `docs/current_state.md`: current project state.
- `docs/current_decisions.md`: decisions already captured from the imported specification.
- `docs/current_architecture.md`: target architecture summary.
- `docs/open_questions.md`: unresolved questions that must be answered before implementation.
- `docs/api/current_contracts.md`: current message and task/result contract references.
- `docs/security_model.md`: runtime security model and acceptance criteria.
- `docs/publication_checklist.md`: public-release confidentiality checklist.
- `docs/mvp_python_quickstart.md`: safe local MVP quickstart contract.
- `docs/mvp_python_configuration.md`: sanitized agent, project, server, and worker configuration examples.
- `docs/nats_private_setup.md`: private NATS setup and subject-permission guidance.
- `docs/worker_server_usage.md`: expected Python server and worker usage contract.
- `docs/security_limits.md`: MVP threat boundary, non-goals, and stop conditions.
- `docs/runtime_scope_rationale.md`: why the local runtime does not replace shared deployment/runtime infrastructure.
- `schemas/task.schema.json`: task JSON Schema.
- `schemas/result.schema.json`: result JSON Schema.

## Quickstart

```bash
python -m pip install -e ".[test]"
python -m pytest -q
codexiachat-agentbus validate-server-config --config examples/server.config.yaml
codexiachat-agentbus validate-worker-config --config examples/worker.config.yaml
```

## Open Source

- License: MIT.
- Security policy: `SECURITY.md`.
- Contribution guide: `CONTRIBUTING.md`.
- Code of conduct: `CODE_OF_CONDUCT.md`.
- Support notes: `SUPPORT.md`.

## Implementation Discipline

- Do not create stubs, mock services, mock messages, or fake data.
- If a dependency, secret, server, agent, or runtime is missing, document the blocker with cause, impact, and unblock path.
- Prefer the imported specification as the source of truth until a newer project decision supersedes it.
- Treat task publication as a privileged remote-execution boundary.
- Enforce scope, paths, command profiles, identity, and replay protection outside Codex prompts.
- Keep the project name as `CodexIAChat`.
- Treat NATS, deployment, dashboard, PostgreSQL, and MCP as future integrations unless their runtime and security controls are explicitly implemented.
