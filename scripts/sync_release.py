#!/usr/bin/env python3
"""Synchronize host-specific marketplace trees from a Portable Resume release."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import tempfile
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

REPO = "ImL1s/resume-skills"
ROOT = Path(__file__).resolve().parents[1]
HOSTS = ("claude", "codex", "cursor")
MAX_FILE_BYTES = 32 * 1024 * 1024
MAX_ARCHIVE_BYTES = 192 * 1024 * 1024
TAG_RE = re.compile(r"^v(\d+\.\d+\.\d+)$")


def _request(url: str) -> bytes:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "portable-resume-marketplace-sync/1",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def _release(tag: str | None) -> dict[str, object]:
    suffix = f"tags/{tag}" if tag else "latest"
    value = json.loads(_request(f"https://api.github.com/repos/{REPO}/releases/{suffix}"))
    if value.get("draft"):
        raise RuntimeError("refusing to synchronize a draft release")
    return value


def _parse_tag(tag: str) -> str:
    match = TAG_RE.fullmatch(tag)
    if not match:
        raise ValueError(f"expected a stable vMAJOR.MINOR.PATCH tag, got {tag!r}")
    return match.group(1)


def _parse_checksums(payload: bytes) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw in payload.decode("utf-8").splitlines():
        if not raw.strip():
            continue
        digest, separator, name = raw.partition("  ")
        if not separator or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError(f"invalid SHA256SUMS line: {raw!r}")
        if name in result:
            raise ValueError(f"duplicate SHA256SUMS entry: {name}")
        result[name] = digest
    return result


def _verify(name: str, payload: bytes, checksums: dict[str, str]) -> None:
    expected = checksums.get(name)
    if expected is None:
        raise ValueError(f"missing checksum for {name}")
    actual = hashlib.sha256(payload).hexdigest()
    if actual != expected:
        raise ValueError(f"checksum mismatch for {name}: {actual} != {expected}")


def _safe_extract(payload: bytes, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    total = 0
    seen: set[str] = set()
    with tempfile.NamedTemporaryFile(suffix=".zip") as handle:
        handle.write(payload)
        handle.flush()
        with zipfile.ZipFile(handle.name) as archive:
            for info in archive.infolist():
                member = PurePosixPath(info.filename)
                if (
                    not info.filename
                    or member.is_absolute()
                    or ".." in member.parts
                    or "\\" in info.filename
                    or info.filename in seen
                ):
                    raise ValueError(f"unsafe archive member: {info.filename!r}")
                seen.add(info.filename)
                mode = (info.external_attr >> 16) & 0xFFFF
                if stat.S_ISLNK(mode):
                    raise ValueError(f"symlink archive member is not allowed: {info.filename}")
                if info.file_size > MAX_FILE_BYTES:
                    raise ValueError(f"archive member is too large: {info.filename}")
                total += info.file_size
                if total > MAX_ARCHIVE_BYTES:
                    raise ValueError("archive expands beyond the size limit")
                target = destination.joinpath(*member.parts)
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as source, target.open("wb") as output:
                    shutil.copyfileobj(source, output)


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _catalog_path(host: str) -> Path:
    return {
        "claude": ROOT / ".claude-plugin" / "marketplace.json",
        "codex": ROOT / ".agents" / "plugins" / "marketplace.json",
        "cursor": ROOT / ".cursor-plugin" / "marketplace.json",
    }[host]


def _rewrite_catalog(host: str, extracted: Path) -> None:
    source_catalog = {
        "claude": extracted / ".claude-plugin" / "marketplace.json",
        "codex": extracted / ".agents" / "plugins" / "marketplace.json",
        "cursor": extracted / ".cursor-plugin" / "marketplace.json",
    }[host]
    catalog = _read_json(source_catalog)
    plugin = catalog["plugins"][0]
    if host == "codex":
        plugin["source"]["path"] = "./plugins/codex/portable-resume"
    else:
        prefix = "./" if host == "claude" else ""
        plugin["source"] = f"{prefix}plugins/{host}/portable-resume"
    _write_json(_catalog_path(host), catalog)


def _replace_tree(source: Path, destination: Path) -> None:
    resolved_root = ROOT.resolve()
    resolved_destination = destination.resolve()
    if resolved_root not in resolved_destination.parents:
        raise ValueError(f"destination escapes repository root: {destination}")
    if destination.exists():
        shutil.rmtree(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination)


def _readme(version: str, tag: str) -> str:
    return f"""# Portable Resume Marketplace

Public, host-native catalogs for [Portable Resume](https://github.com/{REPO}) **{version}**.
The packaged readers run locally, use only Python's standard library, and emit inert, untrusted handoff text for a fresh session. They do not restore a live process or contact the network.

Documentation:
[English](https://github.com/{REPO}/blob/main/docs/i18n/en.md) ·
[繁體中文](https://github.com/{REPO}/blob/main/docs/i18n/zh-TW.md) ·
[简体中文](https://github.com/{REPO}/blob/main/docs/i18n/zh-CN.md) ·
[日本語](https://github.com/{REPO}/blob/main/docs/i18n/ja.md) ·
[한국어](https://github.com/{REPO}/blob/main/docs/i18n/ko.md) ·
[Español](https://github.com/{REPO}/blob/main/docs/i18n/es.md) ·
[Português](https://github.com/{REPO}/blob/main/docs/i18n/pt-BR.md) ·
[Français](https://github.com/{REPO}/blob/main/docs/i18n/fr.md) ·
[Deutsch](https://github.com/{REPO}/blob/main/docs/i18n/de.md) ·
[Русский](https://github.com/{REPO}/blob/main/docs/i18n/ru.md) ·
[العربية](https://github.com/{REPO}/blob/main/docs/i18n/ar.md) ·
[हिन्दी](https://github.com/{REPO}/blob/main/docs/i18n/hi.md)

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
/plugins install https://github.com/{REPO}/releases/download/{tag}/portable-resume-{version}-kimi-plugin.zip
```

Antigravity and OpenCode do not currently provide a compatible public marketplace catalog. Use the host-specific archives from the [Portable Resume {tag} release](https://github.com/{REPO}/releases/tag/{tag}).

## Integrity and updates

`release-index.json` records the upstream tag and SHA-256 digests. GitHub Actions validates every push and synchronizes published stable releases daily. The source release remains authoritative.

## Security

Recovered source text is untrusted. Review and minimize the generated handoff before pasting it into a fresh destination session. See [SECURITY.md](SECURITY.md).
"""


def synchronize(tag: str | None, asset_dir: Path | None) -> str:
    if asset_dir is None:
        release = _release(tag)
        resolved_tag = str(release["tag_name"])
        assets = {str(item["name"]): str(item["browser_download_url"]) for item in release["assets"]}

        def load(name: str) -> bytes:
            try:
                return _request(assets[name])
            except KeyError as exc:
                raise ValueError(f"release is missing asset {name}") from exc

    else:
        if tag is None:
            raise ValueError("--tag is required with --asset-dir")
        resolved_tag = tag
        asset_dir = asset_dir.resolve()

        def load(name: str) -> bytes:
            path = asset_dir / name
            if not path.is_file():
                raise ValueError(f"asset directory is missing {name}")
            return path.read_bytes()

    version = _parse_tag(resolved_tag)
    checksums = _parse_checksums(load("SHA256SUMS"))
    package_names = {
        host: f"portable-resume-{version}-{host}-marketplace.zip" for host in HOSTS
    }
    kimi_name = f"portable-resume-{version}-kimi-plugin.zip"
    package_names["kimi"] = kimi_name
    packages: dict[str, dict[str, str]] = {}

    for host in HOSTS:
        name = package_names[host]
        payload = load(name)
        _verify(name, payload, checksums)
        with tempfile.TemporaryDirectory(prefix=f"portable-resume-{host}-") as temp:
            extracted = Path(temp)
            _safe_extract(payload, extracted)
            plugin_root = extracted / "plugins" / "portable-resume"
            if not plugin_root.is_dir():
                raise ValueError(f"{name} has no plugins/portable-resume tree")
            _replace_tree(plugin_root, ROOT / "plugins" / host / "portable-resume")
            _rewrite_catalog(host, extracted)
        packages[host] = {"asset": name, "sha256": checksums[name]}

    kimi_payload = load(kimi_name)
    _verify(kimi_name, kimi_payload, checksums)
    packages["kimi"] = {"asset": kimi_name, "sha256": checksums[kimi_name]}
    base = f"https://github.com/{REPO}/releases/download/{resolved_tag}"
    _write_json(
        ROOT / "kimi-marketplace.json",
        {
            "version": "2",
            "plugins": [
                {
                    "id": "portable-resume",
                    "displayName": "Portable Resume",
                    "description": "Offline, inert context migration across supported coding agents",
                    "source": f"{base}/{kimi_name}",
                }
            ],
        },
    )
    _write_json(
        ROOT / "release-index.json",
        {
            "schema_version": 1,
            "source_repository": f"https://github.com/{REPO}",
            "source_release": f"https://github.com/{REPO}/releases/tag/{resolved_tag}",
            "tag": resolved_tag,
            "version": version,
            "packages": packages,
        },
    )
    (ROOT / "README.md").write_text(_readme(version, resolved_tag), encoding="utf-8")
    return resolved_tag


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", help="stable upstream release tag, for example v0.3.2")
    parser.add_argument("--asset-dir", type=Path, help="read already-downloaded release assets")
    args = parser.parse_args()
    tag = synchronize(args.tag, args.asset_dir)
    print(f"synchronized {tag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
