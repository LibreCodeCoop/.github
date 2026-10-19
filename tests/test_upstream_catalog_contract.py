# SPDX-FileCopyrightText: 2026 LibreCode coop and contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import unittest
from pathlib import Path

from scripts.render_upstream import check, load_templates


ROOT = Path(__file__).resolve().parents[1]


class UpstreamCatalogContractTest(unittest.TestCase):
    def test_all_committed_patches_render_the_catalog(self) -> None:
        check(load_templates(ROOT / "upstream/templates.json"), ROOT)

    def test_sync_keeps_consumer_release_policy_local(self) -> None:
        content = (ROOT / "workflow-templates/sync-workflow-templates.yml").read_text()
        self.assertIn('cron: "5 2 * * 0"', content)
        self.assertNotIn("nextcloud/server", content)
        self.assertNotIn("steps.freeze", content)
        self.assertIn("uses: ./source/actions/sync-workflows", content)
        self.assertIn("steps.sync.outputs.changed == 'true'", content)

    def test_node_templates_keep_fallbacks_and_use_npm_versions_only(self) -> None:
        for name in (
            "lint-eslint", "lint-stylelint", "lint-typescript",
            "node-test", "npm-build", "openapi",
        ):
            with self.subTest(template=name):
                content = (ROOT / f"workflow-templates/{name}.yml").read_text()
                self.assertIn(".outputs.node-version || '^24'", content)
                self.assertIn(".outputs.package-manager-name == 'npm'", content)
                self.assertIn(".outputs.package-manager-version) || '^11.3'", content)
                self.assertIn('run: npm i -g "npm@$NPM_VERSION"', content)
                self.assertNotIn("run: npm i -g 'npm@${{", content)


if __name__ == "__main__":
    unittest.main()
