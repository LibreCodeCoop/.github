# SPDX-FileCopyrightText: 2026 LibreCode coop and contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Regression tests for a single effective workflow authentication mode."""

import re
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

    def test_job_scope_defines_the_mode_once(self) -> None:
        job = self.content.split("  dispatch:\n", 1)[1]
        resolved = re.findall(
            r"^      AUTH_MODE: .* [|][|] '([^']+)' }}$",
            job, re.MULTILINE,
        )
        self.assertEqual(resolved, ["librecode-app"])
        self.assertIn(
            "    env:\n      AUTH_MODE: ", job
        )
        self.assertEqual(len(re.findall(
            r"^\s*AUTH_MODE:", job, re.MULTILINE
        )), 1)

    def test_app_gates_use_the_resolved_job_mode(self) -> None:
        for name, expected in (
            ("Create LibreCode GitHub App token", "librecode-app"),
            ("Create consumer GitHub App token", "github-app"),
        ):
            with self.subTest(step=name):
                step = self.content.split("      - name: " + name + "\n", 1)[1]
                step = step.split("      - name: ", 1)[0]
                gate = re.findall(
                    r"^\s*if: .*env\.AUTH_MODE == '([^']+)' }}$",
                    step, re.MULTILINE,
                )
                self.assertEqual(gate, [expected])

    def test_validation_and_token_selection_consume_inherited_mode(self) -> None:
        for name in (
            "Validate workflow sync authentication",
            "Resolve workflow sync token",
        ):
            with self.subTest(step=name):
                step = self.content.split("      - name: " + name + "\n", 1)[1]
                step = step.split("      - name: ", 1)[0]
                self.assertIn('case "' + '$' + '{AUTH_MODE}" in', step)
                self.assertNotRegex(step, r"^\s*AUTH_MODE:", re.MULTILINE)

    def test_unset_token_and_app_modes(self) -> None:
        resolved_default = re.search(
            r"^      AUTH_MODE: .* [|][|] '([^']+)' }}$",
            self.content, re.MULTILINE,
        ).group(1)
        gates = {"librecode-app": [], "github-app": []}
        for name, role in (
            ("Create LibreCode GitHub App token", "librecode-app"),
            ("Create consumer GitHub App token", "github-app"),
        ):
            step = self.content.split("      - name: " + name + "\n", 1)[1]
            gates[role] = re.search(
                r"^\s*if: .*env\.AUTH_MODE == '([^']+)' }}$",
                step, re.MULTILINE,
            ).group(1)

        expected = {
            "": (True, False),
            "token": (False, False),
            "librecode-app": (True, False),
            "github-app": (False, True),
            "github-token": (False, False),
        }
        for configured, should_run in expected.items():
            with self.subTest(configured=configured or "(unset)"):
                effective = configured or resolved_default
                actual = (effective == gates["librecode-app"],
                          effective == gates["github-app"])
                self.assertEqual(actual, should_run)


if __name__ == "__main__":
    unittest.main()
