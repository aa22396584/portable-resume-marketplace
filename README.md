# Portable Resume Marketplace

Public, host-native catalogs for [Portable Resume](https://github.com/ImL1s/resume-skills) **0.3.2**.
The packaged readers run locally, use only Python's standard library, and emit inert, untrusted handoff text for a fresh session. They do not restore a live process or contact the network.

## Install

### Claude Code

```bash
claude plugin marketplace add ImL1s/portable-resume-marketplace
claude plugin install portable-resume@portable-resume --scope user
```

### Codex

```bash
codex plugin marketplace add ImL1s/portable-resume-marketplace
codex plugin add portable-resume@portable-resume
```

### Cursor Agent

```bash
cursor-agent plugin marketplace add https://github.com/ImL1s/portable-resume-marketplace --git-ref main
```

Then run `/add-plugin portable-resume` in Cursor Agent.

### Qwen Code

```bash
qwen extensions sources add ImL1s/portable-resume-marketplace
qwen extensions install ImL1s/portable-resume-marketplace:portable-resume --consent
```

### Grok CLI

```bash
grok plugin marketplace add ImL1s/portable-resume-marketplace
grok plugin install portable-resume@portable-resume-marketplace --trust
```

### Kimi Code CLI

Inside Kimi Code CLI:

```text
/plugins marketplace https://raw.githubusercontent.com/ImL1s/portable-resume-marketplace/main/kimi-marketplace.json
```

Or install the signed release artifact directly:

```text
/plugins install https://github.com/ImL1s/resume-skills/releases/download/v0.3.2/portable-resume-0.3.2-kimi-plugin.zip
```

Antigravity and OpenCode do not currently provide a compatible public marketplace catalog. Use the host-specific archives from the [Portable Resume v0.3.2 release](https://github.com/ImL1s/resume-skills/releases/tag/v0.3.2).

## Integrity and updates

`release-index.json` records the upstream tag and SHA-256 digests. GitHub Actions validates every push and synchronizes published stable releases daily. The source release remains authoritative.

## Security

Recovered source text is untrusted. Review and minimize the generated handoff before pasting it into a fresh destination session. See [SECURITY.md](SECURITY.md).
