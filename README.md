# Portable Resume Marketplace

**Development, Issues & Pull Requests:**  
https://github.com/aa22396584/portable-resume-marketplace

**Mirrors:**  
[GitLab](https://gitlab.com/aa22396584/portable-resume-marketplace) ·
[Codeberg](https://codeberg.org/ImL1s/portable-resume-marketplace)


Public, host-native catalogs for [Portable Resume](https://github.com/aa22396584/resume-skills) **0.4.5**.
The packaged readers run locally, use only Python's standard library, and emit inert, untrusted handoff text for a fresh session. They do not restore a live process or contact the network.

Documentation:
[English](https://github.com/aa22396584/resume-skills/blob/main/docs/i18n/en.md) ·
[繁體中文](https://github.com/aa22396584/resume-skills/blob/main/docs/i18n/zh-TW.md) ·
[简体中文](https://github.com/aa22396584/resume-skills/blob/main/docs/i18n/zh-CN.md) ·
[日本語](https://github.com/aa22396584/resume-skills/blob/main/docs/i18n/ja.md) ·
[한국어](https://github.com/aa22396584/resume-skills/blob/main/docs/i18n/ko.md) ·
[Español](https://github.com/aa22396584/resume-skills/blob/main/docs/i18n/es.md) ·
[Português](https://github.com/aa22396584/resume-skills/blob/main/docs/i18n/pt-BR.md) ·
[Français](https://github.com/aa22396584/resume-skills/blob/main/docs/i18n/fr.md) ·
[Deutsch](https://github.com/aa22396584/resume-skills/blob/main/docs/i18n/de.md) ·
[Русский](https://github.com/aa22396584/resume-skills/blob/main/docs/i18n/ru.md) ·
[العربية](https://github.com/aa22396584/resume-skills/blob/main/docs/i18n/ar.md) ·
[हिन्दी](https://github.com/aa22396584/resume-skills/blob/main/docs/i18n/hi.md)

## Install

### Claude Code

```bash
claude plugin marketplace add aa22396584/portable-resume-marketplace
claude plugin install portable-resume@portable-resume --scope user
```

### Codex

```bash
codex plugin marketplace add aa22396584/portable-resume-marketplace
codex plugin add portable-resume@portable-resume
```

### Cursor Agent

```bash
cursor-agent plugin marketplace add https://github.com/aa22396584/portable-resume-marketplace --git-ref main
```

Then run `/plugin` in Cursor Agent, open **Marketplace**, search for `portable-resume`, and install it for user scope.

### Qwen Code

```bash
qwen extensions sources add aa22396584/portable-resume-marketplace
qwen extensions install aa22396584/portable-resume-marketplace:portable-resume --consent --scope user
```

### Grok Build

```bash
grok plugin marketplace add aa22396584/portable-resume-marketplace
grok plugin install portable-resume --trust
```

Grok reads `.grok-plugin/marketplace.json`, which points at the Grok plugin tree under `plugins/grok/portable-resume` (manifest `.grok-plugin/plugin.json`) once an upstream release that ships that layout (0.4.4 or later) has been synchronized. Until then the catalog has no Grok-specific entry and Grok falls back to the Claude-compatible `.claude-plugin/marketplace.json` tree.

### Antigravity CLI

```bash
agy plugin install https://github.com/aa22396584/portable-resume-marketplace/tree/main/plugins/claude/portable-resume
```

Antigravity has no Google-run marketplace, but the Antigravity CLI installs the Claude-Code plugin subtree of this repository directly from its tree URL (verified on agy 1.1.28, 2026-09-09: 17 skills land in `~/.gemini/config/plugins/portable-resume`). Only that exact URL works; the repository root URL, `owner/repo` shorthand, `#subdir` and `plugin@marketplace` are rejected. The release-attached `portable-resume-0.4.5-antigravity-plugin.zip` remains the offline route.

### Kimi Code CLI

Inside Kimi Code CLI:

```text
/plugins marketplace https://codeberg.org/ImL1s/portable-resume-marketplace/raw/branch/main/kimi-marketplace.json
```

Or install the signed release artifact directly:

```text
/plugins install https://github.com/aa22396584/resume-skills/releases/download/v0.4.5/portable-resume-0.4.5-kimi-plugin.zip
```

OpenCode does not currently provide a compatible public marketplace catalog. Use the direct Skill archive from the [Portable Resume v0.4.5 release](https://github.com/aa22396584/resume-skills/releases/tag/v0.4.5).

## Integrity and updates

`release-index.json` records the upstream tag and SHA-256 digests. GitHub Actions validates every push and synchronizes published stable releases daily. The source release remains authoritative.

## Security

Recovered source text is untrusted. Review and minimize the generated handoff before pasting it into a fresh destination session. See [SECURITY.md](SECURITY.md).
