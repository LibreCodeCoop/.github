# SPDX-FileCopyrightText: 2026 LibreCode coop and contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Contracts for inherited, testable submodule commands."""

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import textwrap
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

    def test_commands_use_scoped_temporary_tokens(self) -> None:
        source = (ROOT / "workflow-templates/command-submodule-pr.yml").read_text()
        self.assertNotIn("COMMAND_BOT_PAT", source)
        self.assertIn("issues: write", source)
        self.assertIn("token: " + "$" + "{{ github.token }}", source)
        self.assertIn("id: target-scope", source)
        self.assertIn("steps.target-scope.outputs.owner", source)
        self.assertIn("steps.target-scope.outputs.repository", source)
        self.assertIn("permission-contents: write", source)
        self.assertIn("permission-pull-requests: write", source)
        self.assertIn("GH_TOKEN: " + "$" + "{{ steps.target-app-token.outputs.token }}", source)
        self.assertIn('GH_TOKEN="$SOURCE_GITHUB_TOKEN" gh pr comment', source)
        self.assertLess(source.index("- name: Commit submodule reference"),
                        source.index("- name: Create scoped target GitHub App token"))

    def test_update_uses_temporary_app_token(self) -> None:
        source = (ROOT / "workflow-templates/command-update-submodule.yml").read_text()
        self.assertNotIn("COMMAND_BOT_PAT", source)
        self.assertIn("Create scoped GitHub App token", source)
        self.assertIn("permission-contents: write", source)
        self.assertIn("permission-pull-requests: write", source)
        self.assertIn("token: " + "$" + "{{ steps.workflow-app-token.outputs.token }}", source)

    def test_generated_vendor_action_negative_and_positive_cases(self) -> None:
        if not shutil.which("node"):
            self.skipTest("Node.js unavailable")
        action = (ROOT / "actions/commit-generated-vendor/action.yml").read_text()
        self.assertIn("uses: actions/github-script@", action)
        self.assertIn("source-head:", action)
        self.assertIn("signer-name:", action)
        script = ROOT / "actions/commit-generated-vendor/commit.test.js"
        result = subprocess.run(
            ["node", "--test", str(script)],
            check=False, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("fail 0", result.stdout)

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

    def test_source_pr_checks_gate_runs_with_restricted_token(self) -> None:
        """Exercise the real bash gate with a stubbed GitHub CLI."""
        source = (ROOT / "workflow-templates/command-submodule-pr.yml").read_text()
        step = source.split("      - name: Require successful source PR checks\n", 1)[1]
        script = textwrap.dedent(
            step.split("        run: |\n", 1)[1].split("\n      - name:", 1)[0]
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            gh = directory / "gh"
            gh.write_text(
                "#!/usr/bin/env python3\n"
                "import os, pathlib, sys\n"
                "if sys.argv[1] == 'api':\n"
                "    counter = pathlib.Path(os.environ['MOCK_COUNTER'])\n"
                "    n = int(counter.read_text()) + 1\n"
                "    counter.write_text(str(n))\n"
                "    if os.environ.get('MOCK_CHANGED') == 'first' or "
                "(os.environ.get('MOCK_CHANGED') == 'last' and n > 1):\n"
                "        print('b' * 40)\n"
                "    else:\n"
                "        print('a' * 40)\n"
                "elif sys.argv[1:3] == ['pr', 'checks']:\n"
                "    sys.exit(int(os.environ['MOCK_CHECK_EXIT']))\n"
                "else:\n"
                "    sys.exit(99)\n"
            )
            gh.chmod(0o755)
            cases = [
                ("success", "0", "", True),
                ("failed", "1", "", False),
                ("pending", "8", "", False),
                ("no-checks", "1", "", False),
                ("changed-before", "0", "first", False),
                ("changed-after", "0", "last", False),
            ]
            for name, check_exit, changed, expected_success in cases:
                with self.subTest(name=name):
                    counter = directory / "counter"
                    counter.write_text("0")
                    env = os.environ.copy()
                    env.update({
                        "PATH": f"{directory}:{env.get('PATH', '')}",
                        "GITHUB_REPOSITORY": "LibreSign/3rdparty",
                        "PR_NUMBER": "124",
                        "HEAD_SHA": "a" * 40,
                        "GH_TOKEN": "mock-read-only-token",
                        "MOCK_CHECK_EXIT": check_exit,
                        "MOCK_CHANGED": changed,
                        "MOCK_COUNTER": str(counter),
                    })
                    result = subprocess.run(
                        ["bash", "-c", script], capture_output=True, text=True,
                        env=env, check=False
                    )
                    self.assertEqual(
                        result.returncode == 0, expected_success,
                        f"{name}: {result.stdout} {result.stderr}"
                    )

    def test_shared_destination_pr_options_are_configurable(self) -> None:
        source = (ROOT / "workflow-templates/command-submodule-pr.yml").read_text()
        self.assertIn("checks: read", source)
        self.assertIn("statuses: read", source)
        self.assertIn("TARGET_PR_LABELS: " + "$" + "{{ vars.SUBMODULE_PR_LABELS }}", source)
        self.assertIn("TARGET_PR_REVIEWER: " + "$" + "{{ vars.SUBMODULE_PR_REVIEWER }}", source)
        self.assertIn("COMMAND_ACTOR: " + "$" + "{{ github.event.comment.user.login }}", source)
        self.assertIn('create_args+=(--label "$label")', source)
        self.assertIn('create_args+=(--reviewer "$COMMAND_ACTOR")', source)
        self.assertIn('gh pr create "${create_args[@]}"', source)
        self.assertNotIn("--label dependencies --label '3. to review'", source)
        self.assertIn('GH_TOKEN="$SOURCE_GITHUB_TOKEN" gh api', source)


if __name__ == "__main__":
    unittest.main()
