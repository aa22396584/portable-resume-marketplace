# Portable Resume Marketplace

Public, host-native catalogs for [Portable Resume](https://github.com/ImL1s/resume-skills) **0.4.4**.
The packaged readers run locally, use only Python's standard library, and emit inert, untrusted handoff text for a fresh session. They do not restore a live process or contact the network.

Documentation:
[English](https://github.com/ImL1s/resume-skills/blob/main/docs/i18n/en.md) ·
[繁體中文](https://github.com/ImL1s/resume-skills/blob/main/docs/i18n/zh-TW.md) ·
[简体中文](https://github.com/ImL1s/resume-skills/blob/main/docs/i18n/zh-CN.md) ·
[日本語](https://github.com/ImL1s/resume-skills/blob/main/docs/i18n/ja.md) ·
[한국어](https://github.com/ImL1s/resume-skills/blob/main/docs/i18n/ko.md) ·
[Español](https://github.com/ImL1s/resume-skills/blob/main/docs/i18n/es.md) ·
[Português](https://github.com/ImL1s/resume-skills/blob/main/docs/i18n/pt-BR.md) ·
[Français](https://github.com/ImL1s/resume-skills/blob/main/docs/i18n/fr.md) ·
[Deutsch](https://github.com/ImL1s/resume-skills/blob/main/docs/i18n/de.md) ·
[Русский](https://github.com/ImL1s/resume-skills/blob/main/docs/i18n/ru.md) ·
[العربية](https://github.com/ImL1s/resume-skills/blob/main/docs/i18n/ar.md) ·
[हिन्दी](https://github.com/ImL1s/resume-skills/blob/main/docs/i18n/hi.md)

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

Then run `/plugin` in Cursor Agent, open **Marketplace**, search for `portable-resume`, and install it for user scope.

### Qwen Code

```bash
qwen extensions sources add ImL1s/portable-resume-marketplace
qwen extensions install ImL1s/portable-resume-marketplace:portable-resume --consent --scope user
```

### Grok Build

```bash
grok plugin marketplace add ImL1s/portable-resume-marketplace
grok plugin install portable-resume --trust
```

Grok reads `.grok-plugin/marketplace.json`, which points at the Grok plugin tree under `plugins/grok/portable-resume` (manifest `.grok-plugin/plugin.json`) once an upstream release that ships that layout (0.4.4 or later) has been synchronized. Until then the catalog has no Grok-specific entry and Grok falls back to the Claude-compatible `.claude-plugin/marketplace.json` tree.

### Kimi Code CLI

Inside Kimi Code CLI:

```text
/plugins marketplace https://raw.githubusercontent.com/ImL1s/portable-resume-marketplace/main/kimi-marketplace.json
```

Or install the signed release artifact directly:

```text
/plugins install https://github.com/ImL1s/resume-skills/releases/download/v0.4.4/portable-resume-0.4.4-kimi-plugin.zip
```

Antigravity and OpenCode do not currently provide a compatible public marketplace catalog. Use the host-specific archives from the [Portable Resume v0.4.4 release](https://github.com/ImL1s/resume-skills/releases/tag/v0.4.4).

## Integrity and updates

`release-index.json` records the upstream tag and SHA-256 digests. GitHub Actions validates every push and synchronizes published stable releases daily. The source release remains authoritative.

## Security

Recovered source text is untrusted. Review and minimize the generated handoff before pasting it into a fresh destination session. See [SECURITY.md](SECURITY.md).
