# SPDX-FileCopyrightText: 2026 LibreCode coop and contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import importlib.util
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError


ROOT = Path(__file__).resolve().parents[1]
DISCOVERY = ROOT / "scripts/discover_unprotected_repositories.py"
WORKFLOW = ROOT / ".github/workflows/github-governance-auto-onboard.yml"

spec = importlib.util.spec_from_file_location("baseline_discovery", DISCOVERY)
module = importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def repo(name, *, visibility="public", archived=False, branch="main"):
    return {
        "owner": {"login": "LibreCodeCoop"},
        "name": name,
        "visibility": visibility,
        "archived": archived,
        "private": visibility == "private",
        "default_branch": branch,
    }


class FakeAPI:
    def __init__(self, repositories, rulesets=None, missing_branches=None):
        self.repositories = repositories
        self.existing = rulesets or {}
        self.missing = missing_branches or set()
        self.examined = []

    def list_public_repositories(self, organization):
        assert organization == "LibreCodeCoop"
        return self.repositories

    def rulesets(self, organization, repository):
        self.examined.append(repository)
        return self.existing.get(repository, [])

    def branch_exists(self, organization, repository, branch):
        return repository not in self.missing


class BaselineDiscoveryTest(unittest.TestCase):
    def test_candidate_is_only_initialized_public_repo_without_any_rulesets(self):
        api = FakeAPI(
            [
                repo("z-new"),
                repo("manual", branch="main"),
                repo("inherited"),
                repo("private", visibility="private"),
                repo("archived", archived=True),
                repo("empty", branch=None),
                repo("uninitialized"),
                repo("a-new"),
            ],
            rulesets={"manual": [{"name": "Manual exception"}],
                      "inherited": [{"name": "Protect default and stable branches"}]},
            missing_branches={"uninitialized"},
        )
        result = module.discover(api, "LibreCodeCoop")
        self.assertEqual(result.candidates, ["a-new", "z-new"])
        self.assertEqual(result.exceptions, ["inherited", "manual"])
        self.assertEqual(result.uninitialized, ["empty", "uninitialized"])
        self.assertNotIn("private", api.examined)
        self.assertNotIn("archived", api.examined)

    def test_invalid_repository_name_fails_closed(self):
        api = FakeAPI([repo("evil/path")])
        with self.assertRaisesRegex(ValueError, "Invalid GitHub repository"):
            module.discover(api, "LibreCodeCoop")

    def test_mismatched_owner_fails_closed(self):
        payload = repo("example")
        payload["owner"] = {"login": "attacker"}
        with self.assertRaisesRegex(ValueError, "Unexpected repository owner"):
            module.discover(FakeAPI([payload]), "LibreCodeCoop")

    def test_ruleset_query_error_must_not_be_treated_as_unprotected(self):
        class BrokenAPI(FakeAPI):
            def rulesets(self, organization, repository):
                raise HTTPError("https://api.github.com", 403, "Forbidden", None, None)

        with self.assertRaises(HTTPError):
            module.discover(BrokenAPI([repo("unverified")]), "LibreCodeCoop")

    def test_matrix_size_is_bounded(self):
        api = FakeAPI([repo(f"new-{i}") for i in range(201)])
        with self.assertRaisesRegex(ValueError, "Too many candidates"):
            module.discover(api, "LibreCodeCoop")

    def test_workflow_requires_opt_in_and_never_performs_bulk_reconciliation(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("AUTO_RULESET_ONBOARDING_ENABLED == 'true'", workflow)
        self.assertIn("environment: ruleset-auto-onboard", workflow)
        self.assertIn("onboard-only: 'true'", workflow)
        self.assertIn("permission-administration: write", workflow)
        self.assertIn("repositories: ${{ matrix.repository }}", workflow)
        self.assertIn("max-parallel: 4", workflow)
        self.assertNotIn("pull_request_target:", workflow)
        self.assertNotIn("organization: LibreCodeCoop", workflow.split("Create missing default ruleset only")[1])


if __name__ == "__main__":
    unittest.main()
