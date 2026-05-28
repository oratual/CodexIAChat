# Current Contracts

The authoritative detailed contracts are currently in:

- `docs/specs/agentbus/AGENTBUS_CODEX_MAC_WINDOWS_LINUX.md`

## Message Types

The source specification defines these message types:

- `REQUEST`
- `REPLY`
- `HANDOFF`
- `BLOCKED`
- `ARTIFACT_READY`
- `LOCK`
- `UNLOCK`
- `ERROR`
- `HEARTBEAT`
- `SUMMARY`

## Task Contract

The task JSON contract is defined in section 9 of the source specification.

Any implementation must preserve:

- explicit task identity;
- immutable server-assigned envelope identity;
- source and target agent identity;
- project identity;
- schema version;
- creation and expiry times;
- replay protection through a nonce or monotonic sequence;
- objective and reason;
- allowed files and forbidden scope;
- expected outputs;
- result path;
- timeout and retry constraints.

Workers must reject unknown agents, unknown projects, expired tasks, duplicate task IDs, old nonces/sequences, invalid schema versions, and task bodies whose identity conflicts with the authorized envelope.

## Result Contract

The result JSON contract is defined in section 10 of the source specification.

Any implementation must preserve:

- task identity;
- status;
- worker identity;
- lock fencing token when a lock protected the task;
- summary;
- changed files;
- created artifacts;
- tests run;
- warnings;
- errors;
- follow-up requests when needed.

Result acceptance must re-check changed files and artifacts against the task allowlist and expected outputs before reporting success.

## Change Rule

Do not change these contracts casually. Any contract change must update this file and the source specification or add a newer superseding decision document.
