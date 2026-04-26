"""Regression checks for the hardcoded hackathon demo payloads.

Usage:
    python -m unittest tests.test_hardcoded_demos
"""

from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agentverse_app import codegen


async def _no_sleep(_seconds: float) -> None:
    return None


class HardcodedDemoTests(unittest.TestCase):
    def _demo_for(self, query: str, target_urls: list[str] | None = None) -> dict[str, str]:
        with patch.object(codegen.asyncio, "sleep", _no_sleep):
            files = asyncio.run(
                codegen._check_hardcoded_demos(
                    query,
                    target_urls or ["<all_urls>"],
                    "Judge Demo",
                )
            )
        self.assertIsNotNone(files, query)
        assert files is not None
        return files

    def assert_valid_extension_files(self, files: dict[str, str]) -> None:
        self.assertIn("manifest.json", files)
        self.assertIn("content.js", files)
        manifest = json.loads(files["manifest.json"])
        self.assertEqual(manifest["manifest_version"], 3)

        referenced: set[str] = set()
        for script in manifest.get("content_scripts", []):
            referenced.update(script.get("js", []))
            referenced.update(script.get("css", []))
        for filename in referenced:
            self.assertIn(filename, files)

    def assert_js_syntax_ok(self, source: str) -> None:
        node = shutil.which("node")
        if not node:
            self.skipTest("node is required for JavaScript syntax checks")

        with tempfile.TemporaryDirectory() as tmpdir:
            js_path = Path(tmpdir) / "content.js"
            js_path.write_text(source, encoding="utf-8")
            result = subprocess.run(
                [node, "--check", str(js_path)],
                capture_output=True,
                text=True,
                timeout=10,
            )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_all_demo_triggers_return_valid_extension_payloads(self) -> None:
        cases = [
            ("highlight linkedin hiring internship new grad posts", ["https://www.linkedin.com/*"]),
            ("remove verified blue check spam replies on twitter", ["https://x.com/*"]),
            ("amazon sponsored cheapest de-scammer", ["https://www.amazon.com/*"]),
            ("netflix roulette random episode", ["https://www.netflix.com/*"]),
            ("instagram doomscroll 10 videos", ["https://www.instagram.com/*"]),
            ("youtube clickbait thumbnails", ["https://www.youtube.com/*"]),
            ("youtube focus remove comments distractions", ["https://www.youtube.com/*"]),
            ("twitter community note fact check", ["https://x.com/*"]),
            ("linkedin real talk translate bullshit corporate speak", ["https://www.linkedin.com/*"]),
        ]

        for query, target_urls in cases:
            with self.subTest(query=query):
                files = self._demo_for(query, target_urls)
                self.assert_valid_extension_files(files)
                self.assert_js_syntax_ok(files["content.js"])

    def test_unseen_prompts_receive_relevant_demo_pattern_memory(self) -> None:
        context = codegen._demo_pattern_context(
            "make a calmer youtube watch page",
            ["https://www.youtube.com/*"],
        )
        self.assertIn("Youtube", context)
        self.assertIn("#secondary", context)
        self.assertIn("MutationObserver", context)


if __name__ == "__main__":
    unittest.main()
