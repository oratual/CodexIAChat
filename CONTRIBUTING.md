# Contributing

CodexIAChat is documentation-first until the runtime boundaries are confirmed.

## Before Opening a Change

- Read `README.md`, `SECURITY.md`, and `docs/index.md`.
- Do not add stubs, mock services, fake messages, fake credentials, or placeholder runtime behavior.
- Do not commit `.env` files, logs, `.agentbus/` state, task packs, task results, local hostnames, personal paths, or real infrastructure details.
- If something cannot be implemented safely, document the blocker with cause, impact, and what is needed to unblock it.

## Change Scope

Good initial contributions:

- clarify architecture and contracts;
- improve security guidance;
- add implementation decision records;
- add tests or checks that validate documentation safety;
- refine task/result/message schemas once implementation starts.

Avoid:

- creating a parallel auth, billing, job, storage, deployment, or secret-management layer without an explicit architecture decision;
- adding runtime code that pretends to work without a verified NATS/server/Codex CLI contract;
- embedding private deployment details in docs.

## Pull Request Checklist

- The change has a clear reason.
- No confidential data is included.
- `python -m detect_secrets scan --all-files .` has been run.
- Manual search for obvious sensitive patterns has been run when docs or configs changed.
- Any new operational requirement is documented.

## Commit Style

Use concise imperative commit messages, for example:

- `Add public security policy`
- `Document task result contract`
- `Add secret scan workflow`
