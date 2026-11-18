# SPDX-FileCopyrightText: 2026 LibreCode coop and contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Regression tests for provider-neutral workflow authentication."""

import os
import re
import subprocess
import unittest
from pathlib import Path

WORKFLOW = (
    Path(__file__).resolve().parents[1]
    / "workflow-templates"
    / "sync-workflow-templates.yml"
)


class WorkflowSyncAuthTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.content = WORKFLOW.read_text(encoding="utf-8")

    def step(self, name: str) -> str:
        text = self.content.split("      - name: " + name + "\n", 1)[1]
        return text.split("      - name: ", 1)[0]

    def validation_script(self) -> str:
        step = self.step("Validate workflow sync authentication")
        script = step.split("        run: |\n", 1)[1]
        return "\n".join(
            line[10:] if line.startswith("          ") else line
            for line in script.splitlines()
        ) + "\n"

    def test_public_default_and_one_app_step(self) -> None:
        self.assertIn(
            "AUTH_MODE: " + "$" + "{{ vars.WORKFLOW_SYNC_AUTH_MODE || 'github-app' }}",
            self.content,
        )
        self.assertEqual(
            self.content.count("      - name: Create GitHub App token\n"), 1
        )
        self.assertNotIn("      - name: Create LibreCode GitHub App token\n",
                         self.content)
        self.assertNotIn("      - name: Create consumer GitHub App token\n",
                         self.content)
        self.assertEqual(
            len(re.findall(r"^\s*AUTH_MODE:", self.content, re.MULTILINE)), 1
        )

    def test_app_gate_and_credential_precedence(self) -> None:
        step = self.step("Create GitHub App token")
        self.assertIn(
            "env.AUTH_MODE == 'github-app' || env.AUTH_MODE == 'librecode-app'",
            step,
        )
        self.assertIn(
            "vars.WORKFLOW_SYNC_APP_CLIENT_ID || "
            "vars.LIBRECODE_WORKFLOW_APP_CLIENT_ID", step,
        )
        self.assertIn(
            "secrets.WORKFLOW_SYNC_APP_PRIVATE_KEY || "
            "secrets.LIBRECODE_WORKFLOW_APP_PRIVATE_KEY", step,
        )
        self.assertEqual(self.content.count("id: workflow-app-token"), 1)
        self.assertIn("steps.workflow-app-token.outputs.token",
                      self.step("Resolve workflow sync token"))

    def test_validate_modes_and_credential_pairs(self) -> None:
        script = self.validation_script()
        fixtures = (
            # name, mode, generic ID/key, legacy ID/key, token, success
            ("generic default", "github-app", "id", "key", "", "", "", True),
            ("legacy fallback", "github-app", "", "", "old-id", "old-key", "", True),
            ("legacy mode", "librecode-app", "", "", "old-id", "old-key", "", True),
            ("generic preferred", "github-app", "id", "key", "old-id",
             "old-key", "", True),
            ("partial generic ID", "github-app", "id", "", "old-id",
             "old-key", "", False),
            ("partial generic key", "github-app", "", "key", "old-id",
             "old-key", "", False),
            ("missing app credentials", "github-app", "", "", "", "", "", False),
            ("partial legacy ID", "github-app", "", "", "old-id", "", "", False),
            ("partial legacy key", "github-app", "", "", "", "old-key", "", False),
            ("token", "token", "", "", "", "", "token-value", True),
            ("missing token", "token", "", "", "", "", "", False),
            ("github-token", "github-token", "", "", "", "", "", True),
            ("unsupported", "unrecognized", "", "", "", "", "", False),
        )
        for name, mode, gid, gkey, lid, lkey, token, expected in fixtures:
            with self.subTest(case=name):
                env = dict(os.environ, AUTH_MODE=mode,
                           APP_CLIENT_ID=gid, APP_PRIVATE_KEY=gkey,
                           LEGACY_APP_CLIENT_ID=lid,
                           LEGACY_APP_PRIVATE_KEY=lkey,
                           CONSUMER_TOKEN=token)
                result = subprocess.run(
                    ["bash", "-e", "-c", script], env=env, text=True,
                    capture_output=True, check=False,
                )
                self.assertEqual(
                    result.returncode == 0, expected,
                    name + ": " + result.stderr + result.stdout,
                )

    def test_bash_and_github_expressions_are_well_formed(self) -> None:
        self.assertNotIn(chr(92) + "$" + "{", self.content)
        for line in self.content.splitlines():
            self.assertEqual(line.count("$" + "{{"), line.count("}}"), line)

    def test_token_selection_is_shared(self) -> None:
        step = self.step("Resolve workflow sync token")
        self.assertIn("github-app|librecode-app)", step)
        self.assertIn('token="' + '$' + '{WORKFLOW_APP_TOKEN}"', step)
        self.assertIn('token="' + '$' + '{CONSUMER_TOKEN}"', step)
        self.assertIn('token="' + '$' + '{GITHUB_TOKEN}"', step)
        self.assertNotIn("LIBRECODE_APP_TOKEN", step)


if __name__ == "__main__":
    unittest.main()
