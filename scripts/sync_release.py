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
import unicodedata
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

REPO = "ImL1s/resume-skills"
ROOT = Path(__file__).resolve().parents[1]
# Hosts whose upstream archive is a marketplace tree (catalog + plugins/portable-resume).
HOSTS = ("claude", "codex", "cursor")
# Grok ships a plugin-root archive. It is synchronized only when the archive
# carries the Grok Build manifest layout (upstream 0.4.4+); older releases with
# a root plugin.json are skipped so re-synchronizing them stays byte-identical.
GROK_HOST = "grok"
GROK_MANIFEST = PurePosixPath(".grok-plugin/plugin.json")
DESCRIPTION = "Offline, inert context migration across supported coding agents"
MAX_DOWNLOAD_BYTES = 64 * 1024 * 1024
MAX_FILE_BYTES = 32 * 1024 * 1024
MAX_ARCHIVE_BYTES = 192 * 1024 * 1024
TAG_RE = re.compile(r"^v(\d+\.\d+\.\d+)$")
JsonObject = dict[str, Any]


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
        raw_length = response.headers.get("Content-Length")
        if raw_length is not None:
            try:
                content_length = int(raw_length)
            except ValueError as exc:
                raise ValueError("download has an invalid Content-Length") from exc
            if content_length < 0 or content_length > MAX_DOWNLOAD_BYTES:
                raise ValueError("download exceeds the compressed size limit")
        payload = response.read(MAX_DOWNLOAD_BYTES + 1)
        if len(payload) > MAX_DOWNLOAD_BYTES:
            raise ValueError("download exceeds the compressed size limit")
        return payload


def _release(tag: str | None) -> JsonObject:
    suffix = f"tags/{tag}" if tag else "latest"
    value = json.loads(_request(f"https://api.github.com/repos/{REPO}/releases/{suffix}"))
    if not isinstance(value, dict):
        raise ValueError("GitHub release response must be an object")
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
    seen: dict[str, str] = {}
    with tempfile.NamedTemporaryFile(suffix=".zip") as handle:
        handle.write(payload)
        handle.flush()
        with zipfile.ZipFile(handle.name) as archive:
            for info in archive.infolist():
                member = PurePosixPath(info.filename)
                if (
                    not info.filename
                    or "\x00" in info.filename
                    or member.is_absolute()
                    or ".." in member.parts
                    or "\\" in info.filename
                    or not member.parts
                ):
                    raise ValueError(f"unsafe archive member: {info.filename!r}")
                normalized = member.as_posix()
                collision_key = unicodedata.normalize("NFC", normalized).casefold()
                if collision_key in seen:
                    raise ValueError(
                        "duplicate normalized archive member: "
                        f"{info.filename!r} conflicts with {seen[collision_key]!r}"
                    )
                seen[collision_key] = info.filename
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


def _read_json(path: Path) -> JsonObject:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _catalog_path(host: str) -> Path:
    return {
        "claude": ROOT / ".claude-plugin" / "marketplace.json",
        "codex": ROOT / ".agents" / "plugins" / "marketplace.json",
        "cursor": ROOT / ".cursor-plugin" / "marketplace.json",
        "grok": ROOT / ".grok-plugin" / "marketplace.json",
    }[host]


def _grok_catalog(extracted: Path, version: str) -> JsonObject:
    """Build the Grok Build marketplace catalog from the plugin-root manifest."""

    manifest = _read_json(extracted / Path(*GROK_MANIFEST.parts))
    if manifest.get("name") != "portable-resume" or manifest.get("version") != version:
        raise ValueError("Grok plugin manifest name/version does not match the release")
    author = manifest.get("author")
    if not isinstance(author, dict) or not isinstance(author.get("name"), str):
        raise ValueError("Grok plugin manifest author must be an object with a name")
    plugin: JsonObject = {
        "name": "portable-resume",
        "description": manifest.get("description", DESCRIPTION),
        "version": version,
        "source": f"./plugins/{GROK_HOST}/portable-resume",
        "author": author,
    }
    # Grok documents version/author/homepage/tags/keywords as optional plugin
    # fields; repository and license are extensions it may ignore, kept so the
    # catalog states the license like the Claude/Codex catalogs do.
    for key in ("homepage", "repository", "license", "keywords"):
        if key in manifest:
            plugin[key] = manifest[key]
    return {
        "name": "portable-resume",
        "description": manifest.get("description", DESCRIPTION),
        "owner": author,
        "plugins": [plugin],
    }


def _rewrite_catalog(host: str, extracted: Path) -> JsonObject:
    source_catalog = {
        "claude": extracted / ".claude-plugin" / "marketplace.json",
        "codex": extracted / ".agents" / "plugins" / "marketplace.json",
        "cursor": extracted / ".cursor-plugin" / "marketplace.json",
    }[host]
    catalog = _read_json(source_catalog)
    plugins = catalog.get("plugins")
    if (
        not isinstance(plugins, list)
        or len(plugins) != 1
        or not isinstance(plugins[0], dict)
    ):
        raise ValueError(f"{source_catalog} must contain exactly one plugin object")
    plugin = plugins[0]
    if host == "codex":
        source = plugin.get("source")
        if not isinstance(source, dict):
            raise ValueError(f"{source_catalog} Codex plugin source must be an object")
        source["path"] = "./plugins/codex/portable-resume"
    else:
        prefix = "./" if host == "claude" else ""
        plugin["source"] = f"{prefix}plugins/{host}/portable-resume"
    return catalog


def _version_key(version: str) -> tuple[int, int, int]:
    major, minor, patch = version.split(".")
    return int(major), int(minor), int(patch)


def _validated_packages(value: object, *, label: str) -> dict[str, dict[str, str]]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} packages must be an object")
    result: dict[str, dict[str, str]] = {}
    for host, record in value.items():
        if not isinstance(host, str) or not isinstance(record, dict):
            raise ValueError(f"{label} contains an invalid package record")
        asset = record.get("asset")
        digest = record.get("sha256")
        if not isinstance(asset, str) or not isinstance(digest, str):
            raise ValueError(f"{label} package {host!r} is missing asset/sha256")
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError(f"{label} package {host!r} has an invalid SHA-256")
        result[host] = {"asset": asset, "sha256": digest}
    return result


def _guard_release_transition(
    resolved_tag: str,
    packages: dict[str, dict[str, str]],
    *,
    allow_downgrade: bool,
) -> None:
    index_path = ROOT / "release-index.json"
    if not index_path.is_file():
        return
    current = _read_json(index_path)
    current_tag = current.get("tag")
    current_version = current.get("version")
    if not isinstance(current_tag, str) or not isinstance(current_version, str):
        raise ValueError("existing release-index.json has no valid tag/version")
    parsed_current = _parse_tag(current_tag)
    if parsed_current != current_version:
        raise ValueError("existing release-index.json tag/version mismatch")

    incoming_version = _parse_tag(resolved_tag)
    current_key = _version_key(current_version)
    incoming_key = _version_key(incoming_version)
    if incoming_key < current_key and not allow_downgrade:
        raise ValueError(
            f"refusing marketplace downgrade {current_tag} -> {resolved_tag}; "
            "use --allow-downgrade only for an explicit recovery"
        )
    if incoming_key == current_key:
        current_packages = _validated_packages(
            current.get("packages"), label="existing release index"
        )
        if resolved_tag != current_tag or packages != current_packages:
            raise ValueError(
                f"refusing same-version content divergence for {resolved_tag}"
            )


def _guard_inside_root(destination: Path) -> None:
    resolved_root = ROOT.resolve()
    resolved_destination = destination.resolve()
    if resolved_root not in resolved_destination.parents:
        raise ValueError(f"destination escapes repository root: {destination}")


def _replace_tree(source: Path, destination: Path) -> None:
    _guard_inside_root(destination)
    if destination.exists():
        shutil.rmtree(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination)


def _remove_tree(destination: Path) -> None:
    """Remove a stale synced tree or catalog that the current release lacks."""

    _guard_inside_root(destination)
    if destination.is_dir():
        shutil.rmtree(destination)
    elif destination.exists():
        destination.unlink()


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
/plugins install https://github.com/{REPO}/releases/download/{tag}/portable-resume-{version}-kimi-plugin.zip
```

Antigravity and OpenCode do not currently provide a compatible public marketplace catalog. Use the host-specific archives from the [Portable Resume {tag} release](https://github.com/{REPO}/releases/tag/{tag}).

## Integrity and updates

`release-index.json` records the upstream tag and SHA-256 digests. GitHub Actions validates every push and synchronizes published stable releases daily. The source release remains authoritative.

## Security

Recovered source text is untrusted. Review and minimize the generated handoff before pasting it into a fresh destination session. See [SECURITY.md](SECURITY.md).
"""


def synchronize(
    tag: str | None,
    asset_dir: Path | None,
    *,
    allow_downgrade: bool = False,
) -> str:
    if asset_dir is None:
        release = _release(tag)
        raw_tag = release.get("tag_name")
        raw_assets = release.get("assets")
        if not isinstance(raw_tag, str) or not isinstance(raw_assets, list):
            raise ValueError("GitHub release response is missing tag_name/assets")
        resolved_tag = raw_tag
        assets: dict[str, str] = {}
        for item in raw_assets:
            if not isinstance(item, dict):
                raise ValueError("GitHub release contains a non-object asset")
            name = item.get("name")
            url = item.get("browser_download_url")
            if not isinstance(name, str) or not isinstance(url, str):
                raise ValueError("GitHub release asset is missing name/download URL")
            if name in assets:
                raise ValueError(f"GitHub release contains duplicate asset {name!r}")
            assets[name] = url

        def load(name: str) -> bytes:
            try:
                return _request(assets[name])
            except KeyError as exc:
                raise ValueError(f"release is missing asset {name}") from exc

    else:
        if tag is None:
            raise ValueError("--tag is required with --asset-dir")
        resolved_tag = tag
        resolved_asset_dir = asset_dir.resolve()

        def load(name: str) -> bytes:
            path = resolved_asset_dir / name
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
    payloads: dict[str, bytes] = {}
    packages: dict[str, dict[str, str]] = {
        host: {"asset": name, "sha256": checksums[name]}
        for host, name in package_names.items()
        if name in checksums
    }
    if set(packages) != set(package_names):
        missing = sorted(set(package_names) - set(packages))
        raise ValueError(f"SHA256SUMS is missing package entries: {missing}")
    for host, name in package_names.items():
        payload = load(name)
        _verify(name, payload, checksums)
        payloads[host] = payload

    # The Grok plugin-root archive is optional: absent from older releases, and
    # only adopted when it carries .grok-plugin/plugin.json (upstream 0.4.4+).
    grok_name = f"portable-resume-{version}-{GROK_HOST}-plugin.zip"
    grok_payload: bytes | None = None
    if grok_name in checksums:
        grok_payload = load(grok_name)
        _verify(grok_name, grok_payload, checksums)

    catalogs: dict[str, JsonObject] = {}
    grok_synced = False
    with tempfile.TemporaryDirectory(prefix="portable-resume-sync-") as temp:
        staging = Path(temp)
        for host in HOSTS:
            name = package_names[host]
            extracted = staging / "extracted" / host
            _safe_extract(payloads[host], extracted)
            plugin_root = extracted / "plugins" / "portable-resume"
            if not plugin_root.is_dir():
                raise ValueError(f"{name} has no plugins/portable-resume tree")
            staged_plugin = staging / "plugins" / host / "portable-resume"
            staged_plugin.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(plugin_root, staged_plugin)
            catalogs[host] = _rewrite_catalog(host, extracted)

        if grok_payload is not None:
            extracted = staging / "extracted" / GROK_HOST
            _safe_extract(grok_payload, extracted)
            if (extracted / Path(*GROK_MANIFEST.parts)).is_file():
                if not (extracted / "skills").is_dir():
                    raise ValueError(f"{grok_name} has no skills tree")
                staged_plugin = staging / "plugins" / GROK_HOST / "portable-resume"
                staged_plugin.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(extracted, staged_plugin)
                catalogs[GROK_HOST] = _grok_catalog(extracted, version)
                packages[GROK_HOST] = {"asset": grok_name, "sha256": checksums[grok_name]}
                grok_synced = True

        _guard_release_transition(
            resolved_tag,
            packages,
            allow_downgrade=allow_downgrade,
        )

        # Do not mutate the repository until every archive and catalog has
        # passed checksum, extraction, and schema validation.
        synced_hosts = (*HOSTS, GROK_HOST) if grok_synced else HOSTS
        for host in synced_hosts:
            _replace_tree(
                staging / "plugins" / host / "portable-resume",
                ROOT / "plugins" / host / "portable-resume",
            )
        for host in synced_hosts:
            _write_json(_catalog_path(host), catalogs[host])
        if not grok_synced:
            _remove_tree(ROOT / "plugins" / GROK_HOST)
            _remove_tree(_catalog_path(GROK_HOST).parent)

    base = f"https://github.com/{REPO}/releases/download/{resolved_tag}"
    _write_json(
        ROOT / "kimi-marketplace.json",
        {
            "version": "2",
            "plugins": [
                {
                    "id": "portable-resume",
                    "displayName": "Portable Resume",
                    "description": DESCRIPTION,
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
    parser.add_argument("--tag", help="stable upstream tag, for example v0.3.2")
    parser.add_argument("--asset-dir", type=Path, help="read downloaded release assets")
    parser.add_argument(
        "--allow-downgrade",
        action="store_true",
        help="allow an explicit recovery to an older stable release",
    )
    args = parser.parse_args()
    tag = synchronize(
        args.tag,
        args.asset_dir,
        allow_downgrade=args.allow_downgrade,
    )
    print(f"synchronized {tag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
