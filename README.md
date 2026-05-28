# CodexIAChat

CodexIAChat is a documentation-first project for building an AgentBus-style coordination system between Codex instances on Windows, macOS, and Linux.

The imported source specification is:

- `docs/specs/agentbus/AGENTBUS_CODEX_MAC_WINDOWS_LINUX.md`

Current status: project documentation has been initialized. No runtime service, worker, database schema, or deployment stack has been implemented yet.

## Documentation Entrypoints

- `docs/index.md`: documentation map and reading order.
- `docs/current_state.md`: current project state.
- `docs/current_decisions.md`: decisions already captured from the imported specification.
- `docs/current_architecture.md`: target architecture summary.
- `docs/open_questions.md`: unresolved questions that must be answered before implementation.
- `docs/api/current_contracts.md`: current message and task/result contract references.

## Implementation Discipline

- Do not create stubs, mock services, mock messages, or fake data.
- If a dependency, secret, server, agent, or runtime is missing, document the blocker with cause, impact, and unblock path.
- Prefer the imported specification as the source of truth until a newer project decision supersedes it.
- Keep the project name as `CodexIAChat`.
