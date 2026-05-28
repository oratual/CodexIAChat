# Runtime Scope Rationale

Date: 2026-05-28

Software Memory reported an advisory warning for overlap with protected deploy/secrets/runtime capabilities.

## Decision

Proceed with the CodexIAChat Python MVP as a local/open-source AgentBus runtime package.

## Cause

CodexIAChat needs a minimal runnable server and worker to validate its AgentBus contracts, path enforcement, replay protection, command-profile isolation, result validation, and log redaction.

## Impact

The MVP introduces local runtime code, but it does not deploy infrastructure, manage production secrets, open public ports, replace private shared deployment controls, or create a shared platform runtime.

## Why Reuse Is Not The Best Fit Here

A private shared platform owns production deployment, secrets, shared jobs/files, auth, billing, wallet, analytics, audit, and runtime operations. CodexIAChat is an open-source coordination tool that must be usable outside that private stack, so the local server/worker package is project-owned.

## Guardrails

- No deployment stack is included.
- No real secrets are included.
- NATS is documented as a future private wake-up transport, not faked.
- The MVP binds to loopback/private addresses only.
- Runtime state stays under ignored `.agentbus/` paths by default.
- Production deployment must go through the shared deployment/runtime owner if this is ever installed on private infrastructure.
