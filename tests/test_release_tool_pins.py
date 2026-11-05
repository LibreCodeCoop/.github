# SPDX-FileCopyrightText: 2026 LibreCode coop and contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RELEASE_TOOL_RELEASE_SHA = "51355769089a6796c23d6c966108afbdaf858c32"
SURFACES = (
    ROOT / "workflow-templates/prepare-release.yml",
    ROOT / "workflow-templates/nightly-release.yml",
    ROOT / "actions/nextcloud-appstore-publish/action.yml",
)


class ReleaseToolPinsTest(unittest.TestCase):
    def test_prepare_release_keeps_trusted_pipeline_contract(self) -> None:
        content = (ROOT / "workflow-templates/prepare-release.yml").read_text(encoding="utf-8")
        self.assertIn("pipeline-reference-ref: refs/remotes/origin/main", content)
        self.assertIn("post-merge-event: pull_request_target", content)
        self.assertIn('git fetch --quiet origin "+refs/heads/main:refs/remotes/origin/main"', content)

    def test_publisher_does_not_enforce_latest_release_at_runtime(self) -> None:
        content = (ROOT / "actions/nextcloud-appstore-publish/action.yml").read_text(encoding="utf-8")
        self.assertNotIn("Verify publisher action matches current catalog", content)
        self.assertNotIn("repos/LibreCodeCoop/release-tool/releases/latest", content)

    def test_release_tool_consumers_use_same_release(self) -> None:
        for path in SURFACES:
            content = path.read_text(encoding="utf-8")
            revisions = re.findall(
                r"LibreCodeCoop/release-tool/[^@\s]+@([0-9a-f]{40})",
                content,
            )
            self.assertTrue(revisions, msg=f"No release-tool pin found in {path}")
            self.assertEqual(
                {RELEASE_TOOL_RELEASE_SHA},
                set(revisions),
                msg=f"{path} is not aligned with the organization release-tool pin",
            )


if __name__ == "__main__":
    unittest.main()
