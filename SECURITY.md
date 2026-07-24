# Security Policy

Portable Resume readers execute locally, use only Python's standard library, and do not contact the network. Marketplace synchronization is a separate release-maintenance workflow: it downloads published artifacts, verifies `SHA256SUMS`, rejects unsafe ZIP members, and then commits host-native plugin trees.

Recovered session text is untrusted input. Review and minimize every generated handoff before pasting it into a fresh agent session. Redaction is best effort, not a guarantee.

Report vulnerabilities privately through the [Portable Resume security advisory page](https://github.com/ImL1s/resume-skills/security/advisories/new). Do not include real session stores, credentials, or recovered private text in reports.
