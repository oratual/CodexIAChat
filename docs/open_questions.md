# Open Questions

These must be answered before implementing runtime code.

1. Which Linux host will run the central AgentBus node?
2. Will NATS run inside an existing shared infrastructure stack or a separate stack?
3. Which repository will own shared infrastructure integration if an existing platform is involved?
4. What exact Codex CLI version and command contract will be used for cold execution?
5. What authentication and authorization model should protect task publication?
6. What filesystem paths are canonical on Windows, macOS, and Linux?
7. Which tasks require PostgreSQL in phase 4, and which can remain file-backed?
8. What retention policy applies to task packs, artifacts, results, and logs?
9. What health checks define a working worker, server, and bus?
10. Which acceptance tests must pass before the first runtime deployment?

## Current Blocker For Implementation

Cause: runtime ownership, deployment stack, NATS location, and Codex CLI command contract have not been verified.

Impact: implementing services now would require assumptions that could create throwaway code or incorrect integration boundaries.

Unblock path: confirm runtime host, stack ownership, NATS deployment plan, worker paths, and Codex CLI execution contract.
