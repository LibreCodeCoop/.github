# SPDX-FileCopyrightText: 2026 LibreCode coop and contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import tempfile
import unittest
from pathlib import Path

from scripts.check_workflow_policy import check_file


class WorkflowPolicyTest(unittest.TestCase):
    def write(self, content: str) -> Path:
        temporary = tempfile.NamedTemporaryFile(suffix=".yml", delete=False)
        path = Path(temporary.name)
        temporary.close()
        path.write_text(content, encoding="utf-8")
        self.addCleanup(path.unlink)
        return path

    def test_accepts_pinned_action_and_hardened_checkout(self) -> None:
        path = self.write(
            """
permissions:
  contents: read
steps:
  - uses: actions/checkout@0123456789012345678901234567890123456789 # v4.4.0
    with:
      persist-credentials: false
  - uses: example/action@abcdefabcdefabcdefabcdefabcdefabcdefabcd # 1.2.3
"""
        )
        self.assertEqual(check_file(path), [])

    def test_rejects_mutable_action_revision(self) -> None:
        path = self.write("steps:\n  - uses: example/action@v2\n")
        findings = check_file(path)
        self.assertEqual(len(findings), 1)
        self.assertIn("full 40-character commit SHA", findings[0])

    def test_rejects_checkout_with_persisted_credentials(self) -> None:
        path = self.write(
            """
steps:
  - uses: actions/checkout@0123456789012345678901234567890123456789 # v4.4.0
"""
        )
        findings = check_file(path)
        self.assertEqual(len(findings), 1)
        self.assertIn("persist-credentials: false", findings[0])

    def test_rejects_write_all(self) -> None:
        path = self.write("permissions: write-all\n")
        findings = check_file(path)
        self.assertEqual(len(findings), 1)
        self.assertIn("write-all", findings[0])

    def test_rejects_missing_version_comment_on_external_action(self) -> None:
        path = self.write(
            "steps:\n  - uses: example/action@abcdefabcdefabcdefabcdefabcdefabcdefabcd\n"
        )
        findings = check_file(path)
        self.assertEqual(len(findings), 1)
        self.assertIn("upstream version comment", findings[0])

    def test_rejects_non_version_comment_on_external_action(self) -> None:
        path = self.write(
            "steps:\n  - uses: example/action@abcdefabcdefabcdefabcdefabcdefabcdefabcd # latest\n"
        )
        self.assertIn("upstream version comment", check_file(path)[0])

    def test_accepts_tag_without_v_and_two_component_version(self) -> None:
        path = self.write(
            "steps:\n  - uses: bats-core/bats-action@abcdefabcdefabcdefabcdefabcdefabcdefabcd # 4.0.0\n"
            "  - uses: example/action@0123456789012345678901234567890123456789 # v1.2\n"
        )
        self.assertEqual(check_file(path), [])

    def test_internal_actions_need_source_comment_when_no_release(self) -> None:
        path = self.write(
            "steps:\n  - uses: LibreCodeCoop/release-tool/actions/prepare@"
            "abcdefabcdefabcdefabcdefabcdefabcdefabcd\n"
        )
        self.assertIn("source/version comment", check_file(path)[0])

    def test_internal_pinned_action_allows_descriptive_source_ref(self) -> None:
        path = self.write(
            "steps:\n  - uses: LibreCodeCoop/.github/actions/helpers@"
            "abcdefabcdefabcdefabcdefabcdefabcdefabcd # main at abcdef1\n"
        )
        self.assertEqual(check_file(path), [])

    def test_allows_local_action(self) -> None:
        path = self.write("steps:\n  - uses: ./actions/sync-workflows\n")
        self.assertEqual(check_file(path), [])


if __name__ == "__main__":
    unittest.main()
