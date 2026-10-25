# SPDX-FileCopyrightText: 2026 LibreCode coop and contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import hashlib
import json
import re
import unittest
from pathlib import Path

from scripts.render_upstream import load_templates, render


class NpmAuditWorkflowContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[1]
        cls.upstream_path = cls.root / "upstream/vendor/nextcloud/npm-audit-fix.yml"
        cls.rendered_path = cls.root / "workflow-templates/npm-audit-fix.yml"
        cls.content = cls.rendered_path.read_text(encoding="utf-8")

    def test_upstream_is_pinned_and_unmodified(self) -> None:
        payload = json.loads((self.root / "upstream/sources.json").read_text())
        [source] = [s for s in payload["sources"] if s["name"] == "nextcloud-npm-audit-fix"]
        self.assertEqual(source["repository"], "nextcloud/.github")
        self.assertEqual(source["ref"], "master")
        self.assertEqual(source["path"], "workflow-templates/npm-audit-fix.yml")
        self.assertRegex(source["url"], r"/[0-9a-f]{40}/workflow-templates/npm-audit-fix\.yml$")
        self.assertEqual(
            hashlib.sha256(self.upstream_path.read_bytes()).hexdigest(),
            source["sha256"],
        )

    def test_render_applies_downstream_security_patch_exactly(self) -> None:
        templates = load_templates(self.root / "upstream/templates.json")
        [template] = [t for t in templates if t.name == "nextcloud-npm-audit-fix"]
        self.assertEqual(
            template.patches,
            (Path("patches/nextcloud/npm-audit-fix.yml.patch"),),
        )
        self.assertEqual(render(template, self.root), self.rendered_path.read_bytes())
        self.assertEqual(render(template, self.root), render(template, self.root))

        upstream = self.upstream_path.read_text(encoding="utf-8")
        self.assertIn("enable-pull-request-automerge", upstream)
        self.assertIn("gh pr review --approve", upstream)
        self.assertNotIn("enable-pull-request-automerge", self.content)
        self.assertNotIn("gh pr review --approve", self.content)

    def test_read_only_workflow_with_scoped_short_lived_app_token(self) -> None:
        content = self.content
        self.assertIn("permissions:\n  contents: read\n", content)
        self.assertIn("uses: actions/create-github-app-token@", content)
        self.assertIn("client-id: ${{ vars.LIBRECODE_WORKFLOW_APP_CLIENT_ID }}", content)
        self.assertIn("private-key: ${{ secrets.LIBRECODE_WORKFLOW_APP_PRIVATE_KEY }}", content)
        self.assertIn("permission-contents: write", content)
        self.assertIn("permission-pull-requests: write", content)
        self.assertIn("token: ${{ steps.app-token.outputs.token }}", content)
        self.assertNotIn("COMMAND_BOT_PAT", content)
        self.assertNotIn("AUTOMERGE", content)
        self.assertNotIn("pull-requests: write\n\njobs:", content)
        self.assertNotIn("permission-workflows: write", content)

    def test_reviewable_conventional_pr_and_generic_matrix(self) -> None:
        content = self.content
        self.assertIn("github.event.repository.default_branch", content)
        self.assertIn("matrix.branches != github.event.repository.default_branch", content)
        self.assertIn("fix(deps): resolve npm audit vulnerabilities", content)
        self.assertIn("signoff: true", content)
        self.assertIn("body: ${{ steps.npm-audit.outputs.markdown }}", content)
        self.assertIn("branch: automated/noid/${{ matrix.branches }}-fix-npm-audit", content)
        self.assertNotIn("          - 'stable", content)
        self.assertNotIn("3. to review", content)
        self.assertIn("fallbackNode: '^24'", content)
        self.assertIn("fallbackNpm: '^11.3'", content)
        self.assertEqual(len(re.findall(r"^\s+- name: Create Pull Request$", content, re.M)), 1)


if __name__ == "__main__":
    unittest.main()
