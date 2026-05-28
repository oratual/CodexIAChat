# Security

CodexIAChat is intended for open-source publication.

## Do Not Commit

- Real secrets, tokens, passwords, API keys, SSH keys, certificates, or `.env` files.
- Private hostnames, private IP addresses, internal deployment paths, or personal machine paths unless they are explicitly sanitized examples.
- Runtime task payloads, task results, logs, or `.agentbus/` state that may contain project context.

## Configuration Examples

Use placeholders such as `<server-linux-ip>` and `<replace-with-worker-password>` in documentation. Real values must live outside the repository.

## Pre-Publish Check

Before publishing or pushing sensitive changes, run a secret scan and inspect hits manually. Current baseline: `python -m detect_secrets scan --all-files .` returned no detected secrets on 2026-05-28 after sanitizing the imported specification.
