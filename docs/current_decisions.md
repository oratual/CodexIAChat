# Current Decisions

These decisions are imported from `docs/specs/agentbus/AGENTBUS_CODEX_MAC_WINDOWS_LINUX.md` and should be treated as active unless superseded by a later explicit decision.

## Architecture

- Use a Linux server as the central always-on coordination node.
- Use NATS as the event and wake-up bus.
- Use Markdown and JSON files for heavy context and artifacts.
- Use local workers on Windows and macOS.
- Use Codex CLI, preferably non-interactive execution, for cold task execution.
- Keep MCP optional for a later phase.

## Operational Rules

- Do not automate the Codex graphical client.
- Do not use screen scraping, UI focus automation, click automation, or fragile GUI workflows.
- Do not rely on live Codex chat memory as source of truth.
- Do not make AI agents poll inboxes or watch logs continuously.
- Use structured work packets instead of conversational chat replication.

## Contracts

- Messages should use explicit types such as `REQUEST`, `REPLY`, `HANDOFF`, `BLOCKED`, `ARTIFACT_READY`, `ERROR`, `LOCK`, `UNLOCK`, `HEARTBEAT`, and `SUMMARY`.
- Task packs must include enough context for cold execution.
- Results must be structured and traceable.

## Implementation Order

The source specification defines phased implementation:

1. Minimum bus with files and NATS.
2. AgentBus server.
3. Codex skill.
4. PostgreSQL.
5. Dashboard.
6. MCP.
