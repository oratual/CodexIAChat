# Publication Checklist

Use this checklist before publishing or pushing changes to the public repository.

## Confidentiality

- [ ] No `.env` files are staged.
- [ ] No tokens, API keys, passwords, private keys, certificates, or secret material are staged.
- [ ] No private hostnames, private IP addresses, personal paths, or internal infrastructure details are staged.
- [ ] No `.agentbus/` task packs, results, runtime logs, or JSONL traces are staged.
- [ ] Documentation examples use placeholders such as `<server-linux-ip>`.

## Verification

- [ ] Run `python -m detect_secrets scan --all-files .`.
- [ ] Run a manual sensitive-pattern search when docs or configs changed.
- [ ] Review `git diff --cached` before committing.
- [ ] Confirm GitHub visibility intentionally matches the release plan.

## Runtime Safety

- [ ] No runtime service is added without a verified deployment owner.
- [ ] No NATS listener binds publicly without an explicit security decision.
- [ ] No fake worker, fake server, mock data, or stub behavior is added.
- [ ] Any blocker is documented with cause, impact, and unblock path.
