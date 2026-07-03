# Security Policy

## Reporting a vulnerability

Please do not report security vulnerabilities through public GitHub issues.

Instead, report them privately via the repository's **Security tab → Report a
vulnerability** ([GitHub's private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)).

For assistance or escalation, contact the
[Block Open Source Governance Committee](mailto:open-source-governance@block.xyz).

## Scope notes

model-ledger stores model inventory metadata. A few boundaries worth knowing when
assessing impact:

- The ledger trusts its callers: `record()` accepts arbitrary payloads, and the REST
  API does not ship authentication — deployments are expected to run it behind their
  own auth layer (see the [backends guide](https://block.github.io/model-ledger/guides/backends/)).
- Snapshot hashes provide content addressing and tamper evidence for snapshot
  payloads, not a cryptographic chain over the full event history — see
  [guarantees](https://block.github.io/model-ledger/concepts/guarantees/) for the
  precise integrity model.

## Supported versions

Security fixes land on `main` and ship in the next release; older releases are not
patched retroactively.
