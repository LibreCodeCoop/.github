# SPDX-FileCopyrightText: 2026 LibreCode coop and contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Contracts for inherited, testable submodule commands."""

import hashlib
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

from scripts.render_upstream import check, load_templates

ROOT = Path(__file__).resolve().parents[1]


class SubmoduleCommandTest(unittest.TestCase):
    def test_upstream_provenance_and_rendering(self) -> None:
        manifest = json.loads((ROOT / "upstream/sources.json").read_text())
        expected = {
            "nextcloud-command-submodule-pr": "nextcloud/3rdparty",
        }
        for name, repo in expected.items():
            with self.subTest(name=name):
                item = next(x for x in manifest["sources"] if x["name"] == name)
                self.assertEqual(item["repository"], repo)
                self.assertRegex(item["url"], r"/[0-9a-f]{40}/")
                source = (ROOT / item["destination"]).read_bytes()
                self.assertEqual(hashlib.sha256(source).hexdigest(), item["sha256"])
        check(load_templates(ROOT / "upstream/templates.json"), ROOT)

    def test_no_publish_secrets_during_composer_analysis(self) -> None:
        source = (ROOT / "workflow-templates/command-submodule-pr.yml").read_text()
        process = source.split("  process:\n", 1)[1]
        before_publish = process.split(
            "      - name: Push branch and create target pull request", 1
        )[0]
        self.assertNotIn("secrets.COMMAND_BOT_PAT", before_publish)
        self.assertIn("composer diff --with-links", before_publish)
        self.assertIn("persist-credentials: false", before_publish)
        self.assertIn("gh auth setup-git", process)

    def test_update_is_composite_action_without_pr_checkout(self) -> None:
        workflow = (ROOT / "workflow-templates/command-update-submodule.yml").read_text()
        self.assertNotIn("actions/checkout", workflow)
        self.assertNotIn("git read-tree", workflow)
        self.assertIn("Check actor permission", workflow)
        self.assertRegex(
            workflow,
            r"uses: LibreCodeCoop/\.github/actions/update-submodule@[0-9a-f]{40}",
        )
        action = (ROOT / "actions/update-submodule/action.yml").read_text()
        self.assertIn("uses: actions/github-script@", action)
        self.assertIn("source-repository:", action)
        self.assertIn("submodule-path:", action)
        impl = (ROOT / "actions/update-submodule/update.js").read_text()
        for contract in ("force: false", "Signed-off-by:", "createTree",
                         "createCommit", "updateRef"):
            self.assertIn(contract, impl)

    def test_update_action_negative_and_positive_cases(self) -> None:
        if not shutil.which("node"):
            self.skipTest("Node.js unavailable")
        test_file = ROOT / "actions/update-submodule/update.test.js"
        result = subprocess.run(
            ["node", "--test", str(test_file)],
            check=False, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("fail 0", result.stdout)


if __name__ == "__main__":
    unittest.main()
