# SPDX-FileCopyrightText: 2026 LibreCode coop and contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.sync_upstream import Source, check, load_sources, refresh, sync


class SyncUpstreamTest(unittest.TestCase):
    def test_loads_valid_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "sources.json"
            manifest.write_text(
                json.dumps(
                    {
                        "sources": [
                            {
                                "name": "workflow",
                                "repository": "example/project",
                                "ref": "master",
                                "path": "workflow.yml",
                                "url": "https://raw.githubusercontent.com/example/project/0123456789012345678901234567890123456789/workflow.yml",
                                "sha256": "a" * 64,
                                "destination": "templates/workflow.yml",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            [source] = load_sources(manifest)
            self.assertEqual(source.name, "workflow")
            self.assertEqual(source.repository, "example/project")
            self.assertEqual(source.ref, "master")
            self.assertEqual(source.path, "workflow.yml")
            self.assertEqual(source.destination, Path("templates/workflow.yml"))

    def test_rejects_partial_tracking_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "sources.json"
            manifest.write_text(
                json.dumps(
                    {
                        "sources": [
                            {
                                "name": "workflow",
                                "repository": "example/project",
                                "url": "https://raw.githubusercontent.com/example/project/0123456789012345678901234567890123456789/workflow.yml",
                                "sha256": "a" * 64,
                                "destination": "templates/workflow.yml",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                ValueError, "must define repository, ref and path together"
            ):
                load_sources(manifest)

    def test_rejects_invalid_hash(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "sources.json"
            manifest.write_text(
                json.dumps(
                    {
                        "sources": [
                            {
                                "name": "workflow",
                                "url": "https://example.invalid/commit/workflow.yml",
                                "sha256": "not-a-hash",
                                "destination": "templates/workflow.yml",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "sha256"):
                load_sources(manifest)

    def test_rejects_mutable_raw_github_revision(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "sources.json"
            manifest.write_text(
                json.dumps(
                    {
                        "sources": [
                            {
                                "name": "workflow",
                                "url": "https://raw.githubusercontent.com/example/project/master/workflow.yml",
                                "sha256": "a" * 64,
                                "destination": "templates/workflow.yml",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "40-character Git commit SHA"):
                load_sources(manifest)

    def test_sync_writes_verified_content(self) -> None:
        content = b"name: Example\n"
        source = Source(
            name="workflow",
            url="https://example.invalid/workflow.yml",
            sha256=hashlib.sha256(content).hexdigest(),
            destination=Path("templates/workflow.yml"),
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch("scripts.sync_upstream.fetch", return_value=content):
                sync([source], root)

            self.assertEqual(
                (root / "templates/workflow.yml").read_bytes(),
                content,
            )

    def test_sync_rejects_sha_mismatch_without_writing_destination(self) -> None:
        expected = b"name: Expected\n"
        downloaded = b"name: Unexpected\n"
        source = Source(
            name="workflow",
            url="https://example.invalid/workflow.yml",
            sha256=hashlib.sha256(expected).hexdigest(),
            destination=Path("templates/workflow.yml"),
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            destination = root / "templates/workflow.yml"

            with patch("scripts.sync_upstream._download", return_value=downloaded):
                with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                    sync([source], root)

            self.assertFalse(destination.exists())

    def test_check_detects_drift(self) -> None:
        expected = b"name: Expected\n"
        source = Source(
            name="workflow",
            url="https://example.invalid/workflow.yml",
            sha256=hashlib.sha256(expected).hexdigest(),
            destination=Path("templates/workflow.yml"),
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "templates").mkdir()
            (root / "templates/workflow.yml").write_bytes(b"name: Old\n")

            with patch("scripts.sync_upstream.fetch", return_value=expected):
                with self.assertRaisesRegex(ValueError, "out of date"):
                    check([source], root)

    @patch("scripts.sync_upstream._download")
    @patch("scripts.sync_upstream._latest_commit")
    def test_refresh_updates_pin_hash_and_vendor_copy(
        self, latest_commit, download
    ) -> None:
        latest_commit.return_value = "1" * 40
        content = b"name: Updated\n"
        download.return_value = content

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "sources.json"
            manifest.write_text(
                json.dumps(
                    {
                        "sources": [
                            {
                                "name": "workflow",
                                "repository": "example/project",
                                "ref": "master",
                                "path": "workflow.yml",
                                "url": "https://raw.githubusercontent.com/example/project/0123456789012345678901234567890123456789/workflow.yml",
                                "sha256": "a" * 64,
                                "destination": "templates/workflow.yml",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            refresh(manifest, root, token="token")

            payload = json.loads(manifest.read_text(encoding="utf-8"))
            [source] = payload["sources"]
            self.assertEqual(
                source["url"],
                "https://raw.githubusercontent.com/example/project/"
                + "1" * 40
                + "/workflow.yml",
            )
            self.assertEqual(
                source["sha256"],
                hashlib.sha256(content).hexdigest(),
            )
            self.assertEqual(
                (root / "templates/workflow.yml").read_bytes(),
                content,
            )
            latest_commit.assert_called_once_with(
                "example/project", "master", "workflow.yml", "token"
            )

    @patch("scripts.sync_upstream._download")
    @patch("scripts.sync_upstream._latest_commit")
    def test_refresh_keeps_existing_pin_when_content_is_unchanged(
        self, latest_commit, download
    ) -> None:
        old_commit = "0" * 40
        new_commit = "1" * 40
        content = b"name: Same\n"
        digest = hashlib.sha256(content).hexdigest()
        latest_commit.return_value = new_commit
        download.return_value = content

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "sources.json"
            original_url = (
                "https://raw.githubusercontent.com/example/project/"
                + old_commit
                + "/workflow.yml"
            )
            manifest.write_text(
                json.dumps(
                    {
                        "sources": [
                            {
                                "name": "workflow",
                                "repository": "example/project",
                                "ref": "master",
                                "path": "workflow.yml",
                                "url": original_url,
                                "sha256": digest,
                                "destination": "templates/workflow.yml",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            refresh(manifest, root, token="token")

            payload = json.loads(manifest.read_text(encoding="utf-8"))
            [source] = payload["sources"]
            self.assertEqual(source["url"], original_url)
            self.assertEqual(source["sha256"], digest)
            self.assertEqual((root / "templates/workflow.yml").read_bytes(), content)

    def test_rejects_destination_escape(self) -> None:
        content = b"name: Example\n"
        source = Source(
            name="workflow",
            url="https://example.invalid/workflow.yml",
            sha256=hashlib.sha256(content).hexdigest(),
            destination=Path("../outside.yml"),
        )

        with tempfile.TemporaryDirectory() as directory:
            with patch("scripts.sync_upstream.fetch", return_value=content):
                with self.assertRaisesRegex(ValueError, "unsafe destination"):
                    sync([source], Path(directory))


if __name__ == "__main__":
    unittest.main()
