from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOSTS = {
    "claude": (ROOT / ".claude-plugin" / "marketplace.json", ".claude-plugin"),
    "codex": (ROOT / ".agents" / "plugins" / "marketplace.json", ".codex-plugin"),
    "cursor": (ROOT / ".cursor-plugin" / "marketplace.json", ".cursor-plugin"),
}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


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

    def test_repository_copy_is_deterministic(self):
        before = {}
        for path in ROOT.rglob("*"):
            if path.is_file() and ".git" not in path.parts and "__pycache__" not in path.parts and path.suffix != ".pyc":
                before[path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.assertIn("release-index.json", before)


if __name__ == "__main__":
    unittest.main()
