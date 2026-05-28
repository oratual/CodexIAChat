# Private NATS Setup

NATS is the AgentBus wake-up and event transport. For the MVP it must be private by default and must not be exposed directly to the public internet.

This document gives sanitized configuration examples. Real credentials, certificates, hostnames, private IPs, and deployment paths must stay outside the repository.

## Binding Policy

Allowed MVP bind targets:

- `127.0.0.1` for same-host development.
- A Tailscale address for private cross-machine development.
- A private interface protected by host firewall rules.

Disallowed by default:

- `0.0.0.0`
- public cloud load balancers
- public DNS records
- unauthenticated NATS

Any exception needs an explicit security decision and firewall plan.

## Minimal Private Configuration

```conf
server_name: agentbus-private
host: 127.0.0.1
port: 4222

jetstream {
  store_dir: "<nats-jetstream-dir>"
  max_mem_store: 256Mb
  max_file_store: 2Gb
}

authorization {
  users = [
    {
      user: "agentbus"
      password: "<replace-with-agentbus-password>"
      permissions: {
        publish: {
          allow: [
            "agent.*.wakeup",
            "task.*",
            "lock.*"
          ]
        }
        subscribe: {
          allow: [
            "agent.*.events",
            "agent.*.heartbeat"
          ]
        }
      }
    },
    {
      user: "docs_worker"
      password: "<replace-with-docs-worker-password>"
      permissions: {
        publish: {
          allow: [
            "agent.docs-worker.events",
            "agent.docs-worker.heartbeat"
          ]
        }
        subscribe: {
          allow: [
            "agent.docs-worker.wakeup"
          ]
        }
      }
    }
  ]
}
```

Notes:

- Replace placeholders outside the repository.
- Use one NATS user per agent.
- Keep subject permissions narrow.
- Prefer mTLS when the deployment target and certificate lifecycle are confirmed.

## Subject Model

Recommended MVP subjects:

```txt
agent.<agent-id>.wakeup
agent.<agent-id>.events
agent.<agent-id>.heartbeat
task.<task-id>.status
lock.<project-id>.<resource-id>
```

Rules:

- Workers subscribe only to their own wake subject.
- Workers publish only their own event and heartbeat subjects.
- The server is the only publisher of task wake-ups.
- A task payload must still be fetched and authorized through the server path; NATS wake-ups alone are not authorization.

## Local Verification

Before starting workers:

```bash
nats --server nats://127.0.0.1:4222 --user agentbus --password "<password-from-secret-store>" server check
```

Then verify that worker credentials cannot publish to another worker subject. A failure is expected for unauthorized subjects.

Do not paste real command output containing credentials into docs, issues, task packs, or logs.

## Failure Policy

The server and workers must stop or stay unhealthy when:

- NATS is reachable without authentication;
- the configured NATS address is public;
- subject permissions are broader than the agent registry requires;
- credentials are missing;
- credentials are embedded in repository files;
- replay protection storage is unavailable.
