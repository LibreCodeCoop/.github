# SPDX-FileCopyrightText: 2026 LibreCode coop and contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "governance.config.json"


class GovernanceCiGateContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads(CONFIG.read_text(encoding="utf-8"))

    def test_ci_gate_is_staged_until_its_producer_is_verified(self) -> None:
        gate = self.config["policies"]["required-ci-gate"]
        self.assertEqual(gate["enforcement"], "disabled")
        self.assertEqual(gate["conditions"]["ref_name"]["include"], ["~DEFAULT_BRANCH"])
        self.assertEqual(gate["bypass_actors"], [{
            "actor_id": 0,
            "actor_type": "OrganizationAdmin",
            "bypass_mode": "pull_request",
        }])
        self.assertEqual(gate["rules"], [{
            "type": "required_status_checks",
            "parameters": {
                "required_status_checks": [{"context": "ci-required"}],
                "strict_required_status_checks_policy": True,
                "do_not_enforce_on_create": False,
            },
        }])

    def test_selected_repositories_use_same_policy(self) -> None:
        repositories = self.config["repositories"]
        for name in (
            "LibreCodeCoop/release-tool",
            "LibreCodeCoop/nextcloud-docker-development",
        ):
            with self.subTest(repository=name):
                self.assertEqual(repositories[name]["policies"], ["required-ci-gate"])

    def test_agent_skills_ci_is_scoped_and_uses_real_verified_producer(self) -> None:
        self.assertEqual(
            self.config["repositories"]["LibreCodeCoop/agent-skills"]["policies"],
            ["protected-branches", "agent-skills-ci"],
        )
        gate = self.config["policies"]["agent-skills-ci"]
        self.assertEqual(gate["enforcement"], "active")
        self.assertEqual(gate["conditions"]["ref_name"]["include"], ["~DEFAULT_BRANCH"])
        self.assertEqual(gate["rules"], [{
            "type": "required_status_checks",
            "parameters": {
                "required_status_checks": [{"context": "ci-required"}],
                "strict_required_status_checks_policy": True,
                "do_not_enforce_on_create": False,
            },
        }])
        # Do not accidentally activate the separately staged consumer gate.
        self.assertEqual(self.config["policies"]["required-ci-gate"]["enforcement"], "disabled")

    def test_review_and_existing_governance_checks_stay_separate(self) -> None:
        self.assertEqual(self.config["defaults"]["policies"], ["protected-branches"])
        policies = self.config["policies"]
        for name in ("governance-ci", "organization-config-ci"):
            with self.subTest(policy=name):
                contexts = policies[name]["rules"][0]["parameters"]["required_status_checks"]
                self.assertIn({"context": "DCO"}, contexts)
                self.assertEqual(policies[name]["enforcement"], "active")


if __name__ == "__main__":
    unittest.main()
