# CodexIAChat Security Model

CodexIAChat must be treated as a controlled remote-execution system. A valid task can cause a local worker to run Codex CLI in a project checkout, so security cannot rely on prompts alone.

## Security Goals

- Preserve cross-machine task handoff between trusted agents.
- Prevent public access to the bus, API, task packs, artifacts, and logs.
- Prevent one compromised agent from writing outside its assigned project scope.
- Prevent task content from controlling shell commands, executable paths, environment variables, or secrets.
- Keep enough audit trail to reconstruct what happened without logging sensitive context.
- Fail closed when identity, authorization, schema validation, paths, locks, or result validation are uncertain.

## Threat Model

Primary risks:

- Unauthorized task publication that makes a worker run Codex on attacker-controlled instructions.
- Compromised worker credentials publishing tasks as another agent.
- Prompt injection inside task context causing Codex to ignore allowed scope.
- Path traversal or symlink traversal writing outside the intended checkout.
- Task-supplied command arguments or environment variables becoming command injection.
- Logs, artifacts, or task packs leaking secrets or private project context.
- Replay of old valid messages.
- Advisory locks failing under race conditions.
- Optional HTTP/MCP surfaces becoming broader attack surfaces than NATS.

Out of scope for the first implementation:

- Public internet access.
- Untrusted third-party agents.
- Multi-tenant SaaS operation.
- Browser-based human authentication.

## Required Controls

### Network

- Bind NATS and optional HTTP/MCP APIs to loopback, Tailscale, or a private interface only.
- Do not bind to `0.0.0.0` without a documented security decision and firewall rule.
- Do not expose NATS, task APIs, artifact APIs, worker endpoints, or dashboards directly to the public internet.
- Prefer mTLS for cross-machine transport when feasible. If using NATS user/password initially, enforce per-user subject permissions.

### Identity And Authorization

- Give every agent its own credential.
- For NATS, restrict each agent to the minimum subjects it can publish and subscribe to.
- The server, not the worker prompt, must authorize `from`, `to`, `project`, `allowed_files`, `context_refs`, and `expected_outputs`.
- Workers must reject tasks not addressed to their configured agent identity.
- Rotate credentials after compromise, machine loss, or accidental publication.

### Message Integrity And Replay

Every task envelope should include:

- immutable server-assigned `id`;
- `version`;
- `created_at`;
- `expires_at`;
- source agent;
- target agent;
- project;
- monotonic sequence number or nonce;
- authorization decision reference;
- optional detached signature or server-issued MAC.

Workers must reject:

- expired messages;
- duplicate task IDs;
- old sequence numbers or repeated nonces;
- messages with unknown agents, projects, kinds, or schema versions;
- messages whose envelope identity conflicts with the task body.

### Scope Enforcement

Prompt instructions are not a security boundary. Enforce scope outside Codex:

- Materialize task packs under a dedicated `.agentbus/inbox/<task_id>/` directory.
- Resolve all paths to canonical absolute paths before use.
- Reject absolute paths in task-supplied fields unless they point to explicitly configured coordination directories.
- Reject `..`, home expansion, environment-variable expansion, symlinks escaping the allowed root, and Windows alternate data streams.
- Compare resolved paths against the allowlist before Codex runs and again before accepting results.
- Run each worker under a dedicated OS user with filesystem permissions limited to its project checkout and approved coordination directories.

### Codex CLI Execution

- Use a static command profile owned by worker configuration.
- Do not let task JSON set executable, arguments, environment variables, working directory, sandbox mode, approval mode, or network policy.
- Run Codex with the narrowest practical filesystem and network permissions.
- Do not pass server credentials, NATS credentials, GitHub tokens, deployment secrets, or `.env` values to Codex unless an explicit administrative task requires them.
- Capture stdout/stderr, but redact secrets before persisting logs.
- Enforce wall-clock timeout, output-size limits, and result-file validation.

### Artifacts, Logs, And Retention

- Treat task packs, result files, artifacts, and logs as sensitive by default.
- Keep them out of the public repository.
- Redact known secret patterns before writing logs.
- Store large or sensitive artifacts under a configured artifact root, not arbitrary task-provided paths.
- Apply retention limits for task packs, logs, and artifacts.
- Separate operational logs from task context; logs should reference IDs and paths, not dump full prompts or full artifacts.

### Locks And Concurrency

- Locks must be server-side leases with owner, resource, expiry, and a fencing token.
- Workers must check locks before execution and include the fencing token when submitting results.
- Expired locks may be cleaned up by the server, but a late result with an old fencing token must be rejected.

### Optional HTTP And MCP Surfaces

- Disabled by default until needed.
- Bind only to loopback/private network.
- Require authentication for every endpoint except `/health`.
- Do not enable permissive CORS.
- Apply rate limits and request-size limits.
- Expose artifacts by opaque ID, not raw filesystem path.
- MCP tools must enforce the same authorization, path, and schema checks as NATS/API flows.

## Security Acceptance Criteria

The first runtime implementation is not acceptable until these tests pass:

- Unauthorized agent cannot publish a task to another agent subject.
- Worker rejects task with wrong `to`.
- Worker rejects expired, duplicate, or replayed task.
- Worker rejects path traversal and symlink escape.
- Worker rejects task-supplied executable, arguments, env, or cwd.
- Worker rejects result writing outside `expected_outputs`.
- Worker redacts seeded fake secrets from logs.
- HTTP API, if enabled, rejects unauthenticated state-changing requests.
- Lock fencing rejects stale results.
- Security scan confirms no secrets in repo, task fixtures, logs, or release artifacts.

