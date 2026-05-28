# Current Architecture

CodexIAChat targets an AgentBus architecture for coordinating Codex instances across Windows, macOS, and Linux.

## Target Topology

- Linux server: central coordination node.
- NATS: low-cost event bus and wake-up layer.
- Project folders: source of durable context, artifacts, task packs, and results.
- Windows worker: local executor for Windows/infrastructure tasks.
- macOS worker: local executor for UI/design tasks.
- Codex CLI: execution engine for cold, scoped tasks.

## Primary Components

- `agentbus-server`: central coordinator.
- `nats-server`: message transport.
- `codex-worker-windows`: Windows-side task worker.
- `codex-worker-mac`: macOS-side task worker.
- `agentbus-handoff` Codex skill: disciplined handoff generation and result handling.
- Project `AGENTS.md`: local coordination constraints.
- Optional MCP layer: advanced integration phase.

## Data Shape

The detailed contracts are defined in:

- `docs/specs/agentbus/AGENTBUS_CODEX_MAC_WINDOWS_LINUX.md`
- `docs/api/current_contracts.md`

## Non-Goals

- No GUI automation of Codex.
- No fake worker behavior.
- No stubbed task execution.
- No direct dependency on live chat history.
