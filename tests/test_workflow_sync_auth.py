# SPDX-FileCopyrightText: 2026 LibreCode coop and contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Authentication contract for provider-neutral workflow synchronization."""

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

    def test_default_mode_and_app_action(self) -> None:
        self.assertIn(
            "AUTH_MODE: " + "$" + "{{ vars.WORKFLOW_SYNC_AUTH_MODE || 'github-app' }}",
            self.content,
        )
        action = self.step("Create GitHub App token")
        self.assertIn("env.AUTH_MODE == 'github-app'", action)
        self.assertIn("vars.WORKFLOW_SYNC_APP_CLIENT_ID", action)
        self.assertIn("secrets.WORKFLOW_SYNC_APP_PRIVATE_KEY", action)
        self.assertEqual(self.content.count("      - name: Create GitHub App token\n"), 1)

    def test_resolver_uses_one_app_token(self) -> None:
        action = self.step("Resolve workflow sync token")
        self.assertIn('github-app) token="' + "$" + '{WORKFLOW_APP_TOKEN}"', action)
        self.assertIn('token) token="' + "$" + '{CONSUMER_TOKEN}"', action)
        self.assertIn('github-token) token="' + "$" + '{GITHUB_TOKEN}"', action)
        self.assertIn("steps.workflow-app-token.outputs.token", action)
        self.assertEqual(
            len(re.findall(r"^\s*AUTH_MODE:", self.content, re.MULTILINE)), 1
        )

    def test_validate_credential_modes(self) -> None:
        step = self.step("Validate workflow sync authentication")
        script = step.split("        run: |\n", 1)[1]
        script = "\n".join(
            line[10:] if line.startswith("          ") else line
            for line in script.splitlines()
        ) + "\n"
        cases = (
            ("app valid", "github-app", "client-id", "key", "", True),
            ("app missing id", "github-app", "", "key", "", False),
            ("app missing key", "github-app", "client-id", "", "", False),
            ("app missing both", "github-app", "", "", "", False),
            ("token valid", "token", "", "", "opaque", True),
            ("token missing", "token", "", "", "", False),
            ("github token", "github-token", "", "", "", True),
            ("unsupported mode", "unknown", "", "", "", False),
        )
        for name, mode, client_id, private_key, token, ok in cases:
            with self.subTest(case=name):
                env = dict(
                    os.environ, AUTH_MODE=mode,
                    APP_CLIENT_ID=client_id, APP_PRIVATE_KEY=private_key,
                    CONSUMER_TOKEN=token,
                )
                result = subprocess.run(
                    ["bash", "-e", "-c", script], env=env,
                    capture_output=True, text=True, check=False,
                )
                self.assertEqual(
                    result.returncode == 0, ok,
                    name + ": " + result.stdout + result.stderr,
                )

    def test_action_expressions_are_well_formed(self) -> None:
        self.assertNotIn(chr(92) + "$" + "{", self.content)
        for line in self.content.splitlines():
            self.assertEqual(line.count("$" + "{{"), line.count("}}"), line)


if __name__ == "__main__":
    unittest.main()
