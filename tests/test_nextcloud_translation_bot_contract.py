# SPDX-FileCopyrightText: 2026 LibreCode coop and contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Regression contract for Nextcloud translation-bot direct pushes.

Historic regressions: LibreSign/libresign#8399/#9172 and
LibreCodeCoop/profile_fields#148 / extract#148.
"""

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NEXTCLOUD_BOT = {
    "actor_id": 20296731,
    "actor_type": "User",
    "bypass_mode": "always",
}


class NextcloudTranslationBotContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads((ROOT / "governance.config.json").read_text(encoding="utf-8"))

    def test_all_nextcloud_apps_inherit_default_branch_protection(self):
        config = self.config
        self.assertIn("protected-branches", config["defaults"]["policies"])
        protected = config["policies"]["protected-branches"]
        self.assertEqual(protected["enforcement"], "active")
        self.assertEqual(
            protected["conditions"]["ref_name"]["include"],
            ["~DEFAULT_BRANCH", "refs/heads/stable*"],
        )
        self.assertIn("pull_request", [rule["type"] for rule in protected["rules"]])
        self.assertNotIn(NEXTCLOUD_BOT, protected["bypass_actors"])

    def test_nextcloud_app_marker_adds_direct_push_bypass(self):
        conditions = [
            condition for condition in self.config["conditions"]
            if condition["when"].get("file_exists") == "appinfo/info.xml"
        ]
        self.assertEqual(len(conditions), 1, "Nextcloud marker must have exactly one policy condition")
        self.assertIn(
            NEXTCLOUD_BOT,
            conditions[0]["add_bypass_actors"]["protected-branches"],
        )
        # A condition must not append a separate required-check ruleset that
        # would also block the translation bot, despite the branch bypass.
        self.assertFalse(conditions[0].get("policies"))
        self.assertFalse(conditions[0].get("rulesets"))

    def test_default_ruleset_does_not_introduce_separate_dco_or_ci_gate(self):
        protected = self.config["policies"]["protected-branches"]
        self.assertFalse(
            any(rule["type"] == "required_status_checks" for rule in protected["rules"]),
            "Nextcloud bot must not be blocked by mandatory checks in the common baseline",
        )
        self.assertNotIn("required-ci-gate-active", self.config["defaults"]["policies"])
        self.assertNotIn("required-ci-gate", self.config["defaults"]["policies"])

    def test_new_ci_policy_applies_only_to_homologated_agent_skills(self):
        assignments = self.config["repositories"]
        selected = [
            repo for repo, config in assignments.items()
            if "required-ci-gate-active" in config.get("policies", [])
        ]
        self.assertIn("LibreCodeCoop/agent-skills", selected)
        # Other repositories can adopt the gate only after their own CI is
        # verified; never activate it implicitly for historical bot targets.
        for repo in ("LibreCodeCoop/profile_fields", "LibreCodeCoop/extract"):
            self.assertNotIn("required-ci-gate-active", assignments.get(repo, {}).get("policies", []))

    def test_provisioner_is_creation_only_and_restricted_to_librecode(self):
        workflow = (
            ROOT / ".github/workflows/github-governance-auto-onboard.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("onboard-only: 'true'", workflow)
        self.assertIn("AUTO_RULESET_ONBOARDING_ENABLED == 'true'", workflow)
        self.assertIn("repositories: ${{ matrix.repository }}", workflow)
        self.assertIn("repository: LibreCodeCoop/${{ matrix.repository }}", workflow)
        self.assertNotIn("repository: LibreSign/", workflow)


if __name__ == "__main__":
    unittest.main()
