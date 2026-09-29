# SPDX-FileCopyrightText: 2026 LibreCode coop and contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ACTION = ROOT / "actions/nextcloud-appstore-publish/action.yml"
TEMPLATE = ROOT / "workflow-templates/appstore-build-publish.yml"


class AppStorePublicationContractTest(unittest.TestCase):
    def test_consumer_template_is_thin_wrapper(self) -> None:
        content = TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("LibreCodeCoop/.github/actions/nextcloud-appstore-publish@748b0416ea5b734292671dd0feec33aaf8ec6b82", content)
        self.assertNotIn("\n        run: |", content)
        self.assertLessEqual(len(content.splitlines()), 40)

    def test_external_actions_are_immutable(self) -> None:
        content = ACTION.read_text(encoding="utf-8")
        revisions = re.findall(r"^\s*uses:\s*([^@\s]+)@([^\s#]+)", content, re.MULTILINE)
        self.assertTrue(revisions)
        for action, revision in revisions:
            if action.startswith("./"):
                continue
            self.assertRegex(
                revision,
                r"^[0-9a-f]{40}$",
                msg=f"{action} is not pinned to an immutable SHA: {revision}",
            )

    def test_uses_does_not_interpolate_revisions(self) -> None:
        content = ACTION.read_text(encoding="utf-8")
        for line in content.splitlines():
            if "uses:" in line:
                self.assertNotIn("${{", line)

    def test_manual_recovery_is_release_line_safe(self) -> None:
        content = ACTION.read_text(encoding="utf-8")
        self.assertIn('case "${GITHUB_REF_NAME}" in', content)
        self.assertIn("stable*)", content)
        self.assertIn('git merge-base --is-ancestor "${tag_sha}" "${GITHUB_SHA}"', content)
        self.assertIn('git show "${GITHUB_SHA}:Makefile" > Makefile', content)

    def test_release_source_always_comes_from_tag(self) -> None:
        content = ACTION.read_text(encoding="utf-8")
        self.assertIn("ref: ${{ inputs.release-tag }}", content)
        self.assertIn("require-tag-exists: 'true'", content)

    def test_expression_ids_are_safe(self) -> None:
        content = ACTION.read_text(encoding="utf-8")
        ids = re.findall(r"^\s*id:\s*([^\s]+)", content, re.MULTILINE)
        for step_id in ids:
            self.assertRegex(step_id, r"^[A-Za-z_][A-Za-z0-9_]*$")

    def test_does_not_write_untrusted_values_to_github_env(self) -> None:
        content = ACTION.read_text(encoding="utf-8")
        self.assertNotIn("GITHUB_ENV", content)

    def test_release_upload_uses_runner_cli(self) -> None:
        content = ACTION.read_text(encoding="utf-8")
        self.assertNotIn("svenstaro/upload-release-action", content)
        self.assertIn('gh release upload "${RELEASE_TAG}"', content)

    def test_asset_name_matches_appstore_download_url(self) -> None:
        content = ACTION.read_text(encoding="utf-8")
        self.assertIn('asset_name="${APP_NAME}-${RELEASE_TAG}.tar.gz"', content)
        self.assertIn(
            "releases/download/${{ inputs.release-tag }}/${{ inputs.app-name }}-${{ inputs.release-tag }}.tar.gz",
            content,
        )


if __name__ == "__main__":
    unittest.main()
