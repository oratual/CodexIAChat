# Security Limits

CodexIAChat coordinates remote execution. The MVP must be useful for trusted solo-developer workflows while staying explicit about what it does not protect.

## Trust Boundary

Trusted for the MVP:

- configured server process;
- configured worker identities;
- configured project repositories;
- private local HTTP server for the MVP;
- private NATS network once wake-up transport is implemented;
- operator-managed secrets outside the repository.

Not trusted as security boundaries:

- task prompts;
- Codex model behavior;
- worker chat history;
- task-supplied paths;
- task-supplied command options;
- result JSON before server validation.

## MVP Non-Goals

The MVP does not provide:

- public multi-tenant SaaS isolation;
- browser login or user management;
- public dashboards;
- billing, wallet, or credits;
- untrusted third-party worker execution;
- arbitrary shell command execution from tasks;
- automatic deployment to public infrastructure;
- secret distribution to Codex sessions.

If any of these are needed, add an architecture decision before implementation.

## Required Safety Limits

Network:

- bind server and NATS to loopback or private interfaces;
- keep public ports closed by default;
- require authentication for every state-changing API;
- disable permissive CORS.

Identity:

- one credential per agent;
- no shared server/worker credentials;
- workers reject mismatched `to` identities;
- rotate credentials after exposure.

Filesystem:

- canonicalize all paths;
- reject traversal and symlink escapes;
- keep `.agentbus/` runtime state untracked;
- validate changed files before accepting success.

Execution:

- use static Codex command profiles;
- do not let tasks set executable, args, environment, cwd, sandbox, approval, or network policy;
- enforce timeouts and output-size limits;
- run workers with least practical filesystem permissions.

Logging:

- redact secrets before persistence;
- do not log full prompts by default;
- do not commit logs, task packs, result files, or artifacts containing private context.

## Solo Developer Mode

Solo developer mode may reduce operational complexity, but it does not remove remote-execution risk.

Acceptable simplifications:

- one server;
- one NATS instance;
- one or two workers;
- file-backed task metadata before PostgreSQL;
- loopback-only local development.

Not acceptable simplifications:

- unauthenticated server or NATS;
- public binding for convenience;
- broad filesystem allowlists;
- fake successful task results;
- passing all local environment variables to Codex;
- committing real configs or secrets.

## When To Stop

Stop and document a blocker if:

- the private bind address is unknown;
- credentials are missing or exposed;
- task authorization cannot be enforced outside prompts;
- path canonicalization is not implemented;
- replay protection is unavailable;
- the Codex CLI command contract is unknown;
- result validation cannot verify changed files.

Use the blocker format from `docs/mvp_python_quickstart.md`.
