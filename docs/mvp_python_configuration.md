# MVP Python Configuration

This document defines safe configuration for the Python MVP. The examples in `examples/` are sanitized templates, not committed runtime credentials.

Use placeholders such as `<project-root>`. Real credentials must live outside the repository and be referenced through environment variables.

## Configuration Files

The MVP loads one server config and one worker config:

```txt
<agentbus-config-dir>/
  server.yaml
  worker.<agent-id>.yaml
```

The repository provides templates:

- `examples/server.config.yaml`
- `examples/worker.config.yaml`

## Server Configuration

```yaml
server:
  bind_host: "127.0.0.1"
  port: 8765
  data_dir: ".agentbus/server"
  max_message_bytes: 262144

agents:
  - id: "windows-infra"
    token_env: "AGENTBUS_WINDOWS_INFRA_TOKEN"
    allowed_projects: ["codexiachat"]
    can_submit_tasks: true

  - id: "mac-ui"
    token_env: "AGENTBUS_MAC_UI_TOKEN"
    allowed_projects: ["codexiachat"]

projects:
  - id: "codexiachat"
    repo_path: "<project-root>"
    coordination_roots:
      - "<project-root>/.agentbus"
    artifact_root: "<project-root>/.agentbus/artifacts"
```

Rules:

- `bind_host` must be `127.0.0.1`, a Tailscale address, or another private interface.
- `bind_host: "0.0.0.0"` is rejected by config loading.
- `token_env` is required; do not put real token values in YAML.
- `data_dir` should point outside tracked source or under ignored `.agentbus/`.

## Worker Configuration

```yaml
server:
  url: "http://127.0.0.1:8765"

worker:
  agent_id: "mac-ui"
  project_id: "codexiachat"
  poll_interval_seconds: 5
  redact_logs: true

agents:
  - id: "mac-ui"
    token_env: "AGENTBUS_MAC_UI_TOKEN"
    allowed_projects: ["codexiachat"]
    timeout_seconds: 3600
    command_profile:
      - "codex"
      - "exec"
      - "Use the agentbus-handoff skill. Process {task_file} and write {result_file}."

projects:
  - id: "codexiachat"
    repo_path: "<project-root>"
    coordination_roots:
      - "<project-root>/.agentbus"
    artifact_root: "<project-root>/.agentbus/artifacts"
```

Rules:

- Use one config per worker identity.
- Do not share credentials between server and workers.
- Task JSON must not set executable, arguments, environment, working directory, sandbox policy, approval policy, or network policy.
- The static `command_profile` is owned by worker configuration and reviewed by humans.
- The worker passes only a narrow environment to the command profile by default.
- Do not pass deployment, GitHub, cloud, billing, or database secrets to Codex by default.

## Validation Requirements

Configuration loading fails if:

- required config sections are missing;
- token env var names are missing;
- an agent references an unknown project;
- a worker has no static command profile;
- a worker project is not in the agent allowlist;
- `bind_host` is `0.0.0.0`.
