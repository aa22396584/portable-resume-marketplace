from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import re
import stat
import subprocess
import sys
import tempfile
import unittest
import warnings
import zipfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
HOSTS = {
    "claude": (ROOT / ".claude-plugin" / "marketplace.json", ".claude-plugin"),
    "codex": (ROOT / ".agents" / "plugins" / "marketplace.json", ".codex-plugin"),
    "cursor": (ROOT / ".cursor-plugin" / "marketplace.json", ".cursor-plugin"),
}
SYNC_SPEC = importlib.util.spec_from_file_location(
    "portable_resume_marketplace_sync",
    ROOT / "scripts" / "sync_release.py",
)
assert SYNC_SPEC is not None and SYNC_SPEC.loader is not None
SYNC = importlib.util.module_from_spec(SYNC_SPEC)
SYNC_SPEC.loader.exec_module(SYNC)


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def zip_payload(entries: list[tuple[str | zipfile.ZipInfo, bytes]]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            for name, payload in entries:
                archive.writestr(name, payload)
    return buffer.getvalue()


def build_release_assets(
    root: Path,
    version: str,
    *,
    marker: str = "stable",
    malformed_host: str | None = None,
) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    payloads: dict[str, bytes] = {}
    catalog_paths = {
        "claude": ".claude-plugin/marketplace.json",
        "codex": ".agents/plugins/marketplace.json",
        "cursor": ".cursor-plugin/marketplace.json",
    }
    for host in ("claude", "codex", "cursor"):
        source: object
        if host == "codex":
            source = {"source": "local", "path": "./plugins/portable-resume"}
        else:
            source = "./plugins/portable-resume"
        plugins: list[object] = [{"name": "portable-resume", "source": source}]
        if malformed_host == host:
            plugins = []
        catalog = json.dumps({"plugins": plugins}, sort_keys=True).encode()
        payloads[f"portable-resume-{version}-{host}-marketplace.zip"] = zip_payload(
            [
                (catalog_paths[host], catalog),
                ("plugins/portable-resume/payload.txt", f"{host}:{marker}".encode()),
            ]
        )
    payloads[f"portable-resume-{version}-kimi-plugin.zip"] = zip_payload(
        [("kimi.plugin.json", json.dumps({"version": version}).encode())]
    )
    for name, payload in payloads.items():
        (root / name).write_bytes(payload)
    checksums = "".join(
        f"{hashlib.sha256(payload).hexdigest()}  {name}\n"
        for name, payload in sorted(payloads.items())
    )
    (root / "SHA256SUMS").write_text(checksums, encoding="utf-8")
    return root


def tree_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


class MarketplaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index = read_json(ROOT / "release-index.json")
        cls.version = cls.index["version"]

    def test_catalogs_point_to_host_specific_release_trees(self):
        for host, (catalog_path, manifest_dir) in HOSTS.items():
            with self.subTest(host=host):
                catalog = read_json(catalog_path)
                plugin = catalog["plugins"][0]
                if host == "codex":
                    source = plugin["source"]["path"]
                else:
                    source = plugin["source"]
                self.assertEqual(source.lstrip("./"), f"plugins/{host}/portable-resume")
                manifest = read_json(ROOT / source / manifest_dir / "plugin.json")
                self.assertEqual(manifest["name"], "portable-resume")
                self.assertEqual(manifest["version"], self.version)

    def test_each_plugin_contains_eight_skills(self):
        expected = {
            "resume-antigravity", "resume-claude", "resume-codex", "resume-cursor",
            "resume-grok", "resume-kimi", "resume-opencode", "resume-qwen",
        }
        for host in HOSTS:
            skills = ROOT / "plugins" / host / "portable-resume" / "skills"
            actual = {path.parent.name for path in skills.glob("resume-*/SKILL.md")}
            self.assertEqual(actual, expected, host)

    def test_embedded_runtime_version_matches_release(self):
        for host in HOSTS:
            init_py = ROOT / "plugins" / host / "portable-resume" / "skills" / ".portable-resume" / "runtime" / "portable_resume" / "__init__.py"
            match = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']', init_py.read_text(encoding="utf-8"), re.MULTILINE)
            self.assertIsNotNone(match, init_py)
            self.assertEqual(match.group(1), self.version)

    def test_kimi_catalog_is_pinned_to_release_asset(self):
        catalog = read_json(ROOT / "kimi-marketplace.json")
        plugin = catalog["plugins"][0]
        package = self.index["packages"]["kimi"]["asset"]
        self.assertEqual(catalog["version"], "2")
        self.assertEqual(plugin["id"], "portable-resume")
        self.assertEqual(
            plugin["source"],
            f"https://github.com/ImL1s/resume-skills/releases/download/{self.index['tag']}/{package}",
        )

    def test_release_index_has_sha256_for_all_packages(self):
        self.assertEqual(set(self.index["packages"]), {"claude", "codex", "cursor", "kimi"})
        for value in self.index["packages"].values():
            self.assertRegex(value["sha256"], r"^[0-9a-f]{64}$")

    def test_tree_has_no_symlinks_or_private_absolute_paths(self):
        for path in ROOT.rglob("*"):
            if ".git" in path.parts or "__pycache__" in path.parts or path.suffix == ".pyc":
                continue
            self.assertFalse(path.is_symlink(), path)
            if path.is_file():
                payload = path.read_bytes()
                self.assertNotIn(b"/" + b"Users/", payload, path)
                self.assertNotIn(b"/" + b"home/", payload, path)

    def test_product_copy_does_not_claim_context7_integration(self):
        targets = [ROOT / "README.md", ROOT / "kimi-marketplace.json"]
        targets.extend(ROOT.glob("plugins/*/portable-resume/skills/resume-*/SKILL.md"))
        for path in targets:
            self.assertNotIn("context7", path.read_text(encoding="utf-8").lower(), path)

    def test_installed_entrypoints_are_executable_with_stdlib(self):
        for host in HOSTS:
            root = ROOT / "plugins" / host / "portable-resume" / "skills"
            for runner in sorted(root.glob("resume-*/scripts/run_reader.py")):
                completed = subprocess.run(
                    [sys.executable, str(runner), "--help"],
                    cwd=ROOT,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    timeout=20,
                    check=False,
                )
                self.assertEqual(completed.returncode, 0, f"{runner}: {completed.stdout}")
                self.assertIn("portable-resume", completed.stdout.lower())

    def test_cursor_install_instruction_matches_current_cli(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("run `/plugin` in Cursor Agent", readme)
        self.assertNotIn("/add-plugin", readme)

    def test_readme_keeps_localized_docs_and_explicit_qwen_scope(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for locale in (
            "ar", "de", "en", "es", "fr", "hi", "ja", "ko", "pt-BR", "ru",
            "zh-CN", "zh-TW",
        ):
            self.assertIn(f"/docs/i18n/{locale}.md", readme)
        self.assertIn(
            "qwen extensions install "
            "ImL1s/portable-resume-marketplace:portable-resume "
            "--consent --scope user",
            readme,
        )

    def test_repository_contains_pinned_release_index(self):
        hashes = tree_hashes(ROOT)
        self.assertIn("release-index.json", hashes)


class SynchronizationSecurityTests(unittest.TestCase):
    def test_checksum_mismatch_fails_before_repository_mutation(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            assets = build_release_assets(base / "assets", "0.3.2")
            target = base / "target"
            sentinel = target / "plugins" / "claude" / "portable-resume" / "sentinel.txt"
            sentinel.parent.mkdir(parents=True)
            sentinel.write_text("keep", encoding="utf-8")
            (assets / "portable-resume-0.3.2-cursor-marketplace.zip").write_bytes(
                b"tampered"
            )
            with mock.patch.object(SYNC, "ROOT", target):
                with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                    SYNC.synchronize("v0.3.2", assets)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")

    def test_malformed_catalog_fails_before_repository_mutation(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            assets = build_release_assets(
                base / "assets", "0.3.2", malformed_host="cursor"
            )
            target = base / "target"
            sentinel = target / "plugins" / "claude" / "portable-resume" / "sentinel.txt"
            sentinel.parent.mkdir(parents=True)
            sentinel.write_text("keep", encoding="utf-8")
            with mock.patch.object(SYNC, "ROOT", target):
                with self.assertRaisesRegex(ValueError, "exactly one plugin"):
                    SYNC.synchronize("v0.3.2", assets)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")

    def test_safe_extract_rejects_traversal_symlink_and_collisions(self):
        symlink = zipfile.ZipInfo("link")
        symlink.create_system = 3
        symlink.external_attr = (stat.S_IFLNK | 0o777) << 16
        payloads = {
            "traversal": zip_payload([("../escape", b"x")]),
            "symlink": zip_payload([(symlink, b"target")]),
            "normalized duplicate": zip_payload(
                [("a/b.txt", b"one"), ("a//b.txt", b"two")]
            ),
            "case-folded duplicate": zip_payload(
                [("A.txt", b"one"), ("a.txt", b"two")]
            ),
        }
        for label, payload in payloads.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temp:
                with self.assertRaises(ValueError):
                    SYNC._safe_extract(payload, Path(temp))

    def test_safe_extract_enforces_file_and_total_size_limits(self):
        single = zip_payload([("large.bin", b"xx")])
        aggregate = zip_payload([("a.bin", b"xx"), ("b.bin", b"xx")])
        with tempfile.TemporaryDirectory() as temp:
            with mock.patch.object(SYNC, "MAX_FILE_BYTES", 1):
                with self.assertRaisesRegex(ValueError, "member is too large"):
                    SYNC._safe_extract(single, Path(temp) / "single")
            with (
                mock.patch.object(SYNC, "MAX_FILE_BYTES", 10),
                mock.patch.object(SYNC, "MAX_ARCHIVE_BYTES", 3),
            ):
                with self.assertRaisesRegex(ValueError, "expands beyond"):
                    SYNC._safe_extract(aggregate, Path(temp) / "aggregate")

    def test_checksum_manifest_rejects_duplicate_names(self):
        digest = "0" * 64
        with self.assertRaisesRegex(ValueError, "duplicate SHA256SUMS"):
            SYNC._parse_checksums(
                f"{digest}  same.zip\n{digest}  same.zip\n".encode()
            )

    def test_repeat_synchronization_is_byte_identical(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            assets = build_release_assets(base / "assets", "0.3.2")
            target = base / "target"
            with mock.patch.object(SYNC, "ROOT", target):
                SYNC.synchronize("v0.3.2", assets)
                first = tree_hashes(target)
                SYNC.synchronize("v0.3.2", assets)
                second = tree_hashes(target)
            self.assertEqual(first, second)

    def test_downgrade_and_same_version_divergence_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            stable = build_release_assets(base / "stable", "0.3.2")
            older = build_release_assets(base / "older", "0.3.1")
            divergent = build_release_assets(
                base / "divergent", "0.3.2", marker="different"
            )
            target = base / "target"
            with mock.patch.object(SYNC, "ROOT", target):
                SYNC.synchronize("v0.3.2", stable)
                pinned = (target / "release-index.json").read_bytes()
                with self.assertRaisesRegex(ValueError, "refusing marketplace downgrade"):
                    SYNC.synchronize("v0.3.1", older)
                with self.assertRaisesRegex(
                    ValueError, "same-version content divergence"
                ):
                    SYNC.synchronize("v0.3.2", divergent)
            self.assertEqual((target / "release-index.json").read_bytes(), pinned)

    def test_explicit_downgrade_is_available_only_by_flag(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            stable = build_release_assets(base / "stable", "0.3.2")
            older = build_release_assets(base / "older", "0.3.1")
            target = base / "target"
            with mock.patch.object(SYNC, "ROOT", target):
                SYNC.synchronize("v0.3.2", stable)
                SYNC.synchronize("v0.3.1", older, allow_downgrade=True)
            self.assertEqual(read_json(target / "release-index.json")["tag"], "v0.3.1")

    def test_sync_workflow_checks_existing_tag_index(self):
        workflow = (ROOT / ".github" / "workflows" / "sync.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn('git show "$tag:release-index.json"', workflow)
        self.assertIn('cmp -s "$tagged_index" release-index.json', workflow)


if __name__ == "__main__":
    unittest.main()
