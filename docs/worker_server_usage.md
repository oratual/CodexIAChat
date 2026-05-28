# Worker And Server Usage

This document defines usage for the Python MVP server and workers.

## Server Responsibilities

`codexiachat-agentbus server` must:

- load agent and project registries;
- authenticate task publishers with bearer tokens loaded from environment variables;
- authorize `from`, `to`, `project`, `allowed_files`, `context_refs`, and `expected_outputs`;
- reject expired, duplicate, malformed, or replayed tasks;
- persist task metadata outside the public repository;
- expose pending authorized tasks only after server-side admission;
- validate result files before marking a task successful.

The server must not trust worker prompts, task body identity, or task-supplied paths as security boundaries.

## Worker Responsibilities

`codexiachat-agentbus worker-run-once` must:

- load exactly one configured `agent_id`;
- fetch pending tasks through the server;
- reject tasks not addressed to the configured agent;
- materialize each task under `<project-root>/.agentbus/inbox/<task_id>/`;
- run Codex CLI only through the configured static command profile;
- validate the result file under `<project-root>/.agentbus/outbox/`;
- compare actual changed files against `expected_outputs`;
- publish status without dumping full prompts or secrets.

## Commands

```bash
codexiachat-agentbus server --config <agentbus-config-dir>/server.yaml
codexiachat-agentbus validate-server-config --config <agentbus-config-dir>/server.yaml
codexiachat-agentbus validate-worker-config --config <worker-config-file>
codexiachat-agentbus submit-task --config <agentbus-config-dir>/server.yaml --actor windows-infra --task <task-request-file>
codexiachat-agentbus worker-run-once --config <worker-config-file>
```

## Health Checks

Server health:

```json
{
  "ok": true
}
```

Do not include secrets, local usernames, full environment variables, task prompts, or credential paths in health output.

## Task Request Requirements

A task request must include:

- source agent;
- target agent;
- project;
- objective summary;
- reason;
- allowed files;
- forbidden scope;
- expected outputs;
- context references;
- expiry;
- nonce.

The server rejects task requests that:

- reference unknown agents or projects;
- include absolute paths outside configured roots;
- include path traversal;
- request broad filesystem access;
- provide command arguments or environment variables;
- omit expected outputs;
- conflict with protected scopes.

## Result Requirements

A worker result must include:

- task ID;
- worker identity;
- status;
- changed files;
- created artifacts;
- tests run;
- warnings;
- errors;
- lock fencing token when applicable.

The server re-checks changed files and artifacts against the authorized task before accepting success. The worker also checks actual filesystem changes after command execution.

## Operational Usage

For local development:

1. Start the server on `127.0.0.1`.
2. Submit one real low-risk documentation task.
3. Run one worker cycle.
4. Inspect server state, worker logs, result JSON, and Git diff.
5. Run tests and the publication checklist before committing docs or examples.

For cross-machine development:

1. Use a private network address.
2. Use per-agent credentials.
3. Add NATS subject permissions once NATS wake-up transport is implemented.
4. Keep server, NATS, and worker configs out of the public repo.
5. Run only tasks whose project and paths are explicitly registered.

## No Fake Success

The MVP must not mark work successful because a worker process received a task. Success requires a real command-profile run, a valid result JSON, post-execution changed-file validation, and server-side result acceptance.
