# CodexIAChat Security Review

Date: 2026-05-28

## Executive Summary

CodexIAChat can keep its planned functionality, but it must be implemented as a controlled remote-execution system. The strongest security posture is not to remove handoffs or Codex CLI execution; it is to enforce identity, authorization, path scope, command profiles, replay protection, and log hygiene outside the model.

No live runtime code exists yet, so the current risk is architectural: if the first implementation follows the original specification too loosely, NATS/API task publication could become an unauthenticated or over-authorized way to make workers execute Codex against local projects.

## Critical Findings

### C-1. Task Publication Is Equivalent To Remote Execution

Impact: any actor that can publish a valid task to a worker can cause Codex CLI to operate inside a project checkout.

Evidence: `docs/specs/agentbus/AGENTBUS_CODEX_MAC_WINDOWS_LINUX.md` describes workers subscribing to NATS and running Codex CLI for task packs. Security controls exist, but before this review they did not explicitly state that task publication is a remote-execution boundary.

Required fix:

- Treat NATS/API task submission as privileged.
- Require per-agent identity and per-subject authorization.
- Validate source, target, project, paths, outputs, expiry, and schema server-side before a worker sees the task.
- Reject tasks by default when authorization context is incomplete.

Status: documented in `docs/security_model.md`.

### C-2. Prompt Scope Is Not A Security Boundary

Impact: a malicious or compromised task context could instruct Codex to ignore the allowed scope unless the worker enforces scope independently.

Evidence: the specification includes `allowed_files` and `forbidden_scope`, but those are partly expressed as task instructions. That is useful for behavior, not sufficient for enforcement.

Required fix:

- Canonicalize and validate all paths before execution.
- Run workers under dedicated OS users.
- Check created/modified files after execution before accepting results.
- Reject symlink escapes, absolute path injection, `..`, home expansion, and environment expansion.

Status: documented in `docs/security_model.md`.

## High Findings

### H-1. NATS Needs Subject-Level Permissions, Not Only Credentials

Risk: one leaked or overbroad credential could publish tasks to any worker.

Required fix:

- Use one credential per agent.
- Limit publish/subscribe permissions by subject.
- Bind NATS only to loopback, Tailscale, or a private interface.
- Prefer mTLS later; user/password is acceptable only for the first private-network phase if permissions are strict.

### H-2. Replay And Duplicate Task Protection Is Not Yet A Contract Requirement

Risk: a captured old task could be replayed and executed again.

Required fix:

- Add server-assigned immutable IDs.
- Track processed task IDs.
- Require `created_at`, `expires_at`, and nonce or monotonic sequence.
- Reject duplicate IDs, expired messages, and old nonces/sequences.

### H-3. Codex CLI Command Must Be Static Worker Configuration

Risk: task-supplied executable, arguments, working directory, environment, sandbox, or approval mode would become command injection.

Required fix:

- Worker owns executable, args, cwd, environment, sandbox, approval policy, timeout, and network policy.
- Task JSON can only choose from pre-approved command profiles if needed.
- Codex must not receive NATS, server, GitHub, deployment, or `.env` secrets by default.

### H-4. Optional HTTP/MCP APIs Need Secure Defaults

Risk: optional APIs can become public control planes if enabled casually.

Required fix:

- Disable by default.
- Bind to loopback/private network.
- Authenticate every endpoint except `/health`.
- No permissive CORS.
- Rate-limit and size-limit requests.
- Expose artifacts by opaque ID instead of path.

## Medium Findings

### M-1. Artifacts And Logs Can Leak Sensitive Context

Risk: task packs, Codex stdout/stderr, results, and artifacts may contain project internals or secrets.

Required fix:

- Treat all `.agentbus/`, logs, task packs, and artifacts as sensitive.
- Keep them out of Git.
- Redact secrets before persistence.
- Use retention windows.
- Log IDs and state transitions rather than dumping full prompts or artifacts.

### M-2. Locks Need Fencing Tokens

Risk: expired locks and late workers can still produce stale writes.

Required fix:

- Locks should be server-side leases with owner, expiry, and fencing token.
- Results must include the token.
- Server rejects stale-token results.

### M-3. Public Repo Hygiene Is Good But Should Stay Separate From Runtime Security

Risk: passing secret scans can create false confidence.

Required fix:

- Continue CI secret scans.
- Add runtime security tests before implementing workers/server.
- Do not commit real configs, task packs, logs, or deployment details.

## Recommended First Implementation Baseline

1. Private network only.
2. NATS per-agent credentials with subject ACLs.
3. Server-side task authorization before publish.
4. Worker-side identity, schema, expiry, replay, and path validation.
5. Static Codex command profile.
6. Dedicated worker OS user per project.
7. No secrets in Codex environment by default.
8. Artifact/log redaction and retention.
9. HTTP/MCP disabled until a concrete need exists.
10. Security acceptance tests from `docs/security_model.md`.

## Conclusion

The project does not need to lose functionality. The safe design is a two-layer model: the bus enables coordination, but workers enforce local execution boundaries mechanically before and after Codex runs.
