# MVP Python Quickstart

This guide defines the safe local quickstart for the Python MVP.

Current repository state: a Python runtime package exists under `src/codexiachat/agentbus`. It provides a private HTTP admission server and a `worker-run-once` flow. NATS is still the planned wake-up transport and is not faked by this MVP.

## Goal

The local MVP must prove this minimum flow without public exposure or fake execution:

1. Start `agentbus-server` with explicit agent and project registries.
2. Start one local `codex-worker` bound to one configured agent identity.
3. Submit one real task addressed to that worker.
5. Materialize a task pack under the configured project `.agentbus/inbox/<task_id>/`.
6. Run Codex CLI through a static worker-owned command profile.
7. Validate and publish a structured result.

If any step is missing, the implementation must fail closed with a warning that includes cause, impact, and the unblock requirement.

## Local Prerequisites

- Python version selected by the runtime implementation, documented in `pyproject.toml`.
- NATS server is optional for the current MVP and required for the later wake-up transport.
- Codex CLI installed on the worker machine.
- A project checkout selected for the worker.
- Agent and project registries stored outside secrets.
- Credentials stored outside the repository.

Do not commit virtual environments, `.env` files, NATS credentials, task packs, results, logs, or local `.agentbus/` runtime state.

## Expected Repository Setup

Local development setup:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
```

If `pyproject.toml` does not exist, stop and document the blocker instead of creating ad hoc install commands.

## Expected Local Start Order

1. Export the token env vars referenced by your config.
2. Validate server and worker configs.
3. Start `codexiachat-agentbus server --config <server.yaml>`.
4. Check `GET /health`.
5. Submit a real task through `codexiachat-agentbus submit-task`.
6. Run one worker cycle with `codexiachat-agentbus worker-run-once --config <worker.yaml>`.

The server must assign immutable task identity and authorization metadata. Workers must not accept direct task JSON that bypasses the server authorization path.

## Expected Smoke Test

A valid smoke test uses a real repository file allowed by the project registry, for example:

```txt
Objective: update one documentation file listed in allowed_files.
Allowed files:
- <project-root>/docs/<allowed-document>.md
Expected outputs:
- <project-root>/.agentbus/outbox/<task_id>.result.json
```

The test must not use fake workers, fake server responses, synthetic successful results, or committed task packs.

## Success Criteria

- The server binds to loopback or a private address.
- Worker accepts only tasks addressed to its configured identity.
- Worker rejects expired, duplicate, or unauthorized tasks.
- Worker runs Codex CLI only through static command configuration.
- Changed files match the task allowlist.
- Result JSON validates against `docs/api/current_contracts.md`.
- Logs are redacted before persistence.
- No secrets or local runtime state are staged in Git.

## Blocker Format

Use this warning format when the quickstart cannot proceed:

```txt
WARNING: <short blocker>
Cause: <specific missing dependency or unsafe condition>
Impact: <what cannot be validated>
Unblock: <exact decision, credential, file, service, or implementation needed>
```
