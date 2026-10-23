# SPDX-FileCopyrightText: 2026 LibreCode coop and contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NIGHTLY = ROOT / "workflow-templates/nightly-release.yml"
PUBLISH = ROOT / "actions/nextcloud-appstore-publish/action.yml"
PREPARE = ROOT / "workflow-templates/prepare-release.yml"


class ReleaseWorkflowArchitectureTest(unittest.TestCase):
    def test_metadata_and_authorization_delegate_to_testable_php_adapters(self) -> None:
        for path in (NIGHTLY, PUBLISH):
            with self.subTest(path=path.name):
                content = path.read_text()
                self.assertIn("release-tool/actions/build-inspect@", content)
                self.assertIn("outputs.has-package-json == 'true'", content)
                self.assertNotIn("python3", content)
                self.assertNotIn("skjnldsv/", content)
                self.assertNotIn("read-package-engines-version-actions", content)
                self.assertNotIn("xpath-action", content)
        self.assertIn("release-tool/actions/authorization-check@", PUBLISH.read_text())

    def test_nightly_only_uses_latest_stable_and_checked_out_sha(self) -> None:
        content = NIGHTLY.read_text()
        self.assertIn("cron: '17 3 * * *'", content)
        self.assertNotIn("\n  push:\n", content)
        self.assertIn("if: needs.resolve-latest-stable.outputs.latest-branch != ''", content)
        self.assertIn("ref: ${{ needs.resolve-latest-stable.outputs.latest-branch }}", content)
        self.assertIn('sha=$(git rev-parse HEAD)', content)
        self.assertIn('sha="${{ steps.source.outputs.sha }}"', content)
        self.assertIn('node-version: ${{ steps.build_metadata.outputs.node-version }}', content)
        self.assertIn('NPM_VERSION: ${{ steps.build_metadata.outputs.npm-version }}', content)
        self.assertIn('run: npm i -g "npm@${NPM_VERSION}"', content)

    def test_prepare_release_preserves_privileged_event_guards(self) -> None:
        content = PREPARE.read_text()
        self.assertIn("github.event.pull_request.merged == true", content)
        self.assertIn("startsWith(github.event.pull_request.head.ref, 'release-tool/')", content)
        self.assertIn("contains(github.event.pull_request.body, '<!-- release-tool:preparation ')", content)
        self.assertNotIn("paths-ignore:", content)

    def test_action_pins_are_immutable(self) -> None:
        for path in (NIGHTLY, PUBLISH, PREPARE):
            with self.subTest(file=path.name):
                content = path.read_text()
                self.assertNotIn("RELEASE_SHA_PENDING", content)
                for line in content.splitlines():
                    if re.search(r"^\s*uses: LibreCodeCoop/release-tool/", line):
                        self.assertRegex(line, r"@[0-9a-f]{40}\s+#\s+v?\d+\.\d+\.\d+$")


if __name__ == "__main__":
    unittest.main()
