#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 LibreCode coop and contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from typing import NamedTuple
from pathlib import Path

LOCK_HEADER = (
    "# SPDX-FileCopyrightText: 2025 Nextcloud GmbH and Nextcloud contributors\n"
    "# SPDX-" + "License-Identifier: MIT\n"
)
LOCK_SCHEMA_HEADER = "# workflow-lock-schema: 3\n"


class LockEntry(NamedTuple):
    workflow: str
    algorithm: str
    digest: str
    catalog_commit: str = ""
    legacy_provenance: bool = False

    def to_json(self) -> str:
        payload = {
            "workflow": self.workflow,
            "sha256": self.digest,
            "catalog_commit": self.catalog_commit,
        }
        return json.dumps(payload, separators=(",", ":"), ensure_ascii=True)


def md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes(), usedforsecurity=False).hexdigest()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _valid_hex(value: str, length: int) -> bool:
    return len(value) == length and all(
        character in "0123456789abcdef" for character in value
    )


def parse_lock_records(path: Path) -> dict[str, LockEntry]:
    if not path.is_file():
        return {}

    entries: dict[str, LockEntry] = {}
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        if line.startswith("{"):
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"invalid lock JSON at line {line_number}"
                ) from error

            if not isinstance(payload, dict):
                raise ValueError(f"invalid lock entry at line {line_number}")

            workflow = payload.get("workflow")
            digest = payload.get("sha256")
            if not isinstance(workflow, str) or not workflow:
                raise ValueError(f"invalid workflow at line {line_number}")
            if not isinstance(digest, str) or not _valid_hex(digest, 64):
                raise ValueError(f"invalid SHA-256 at line {line_number}")

            entry = LockEntry(
                workflow=workflow,
                algorithm="sha256",
                digest=digest,
                catalog_commit=str(payload.get("catalog_commit", "")),
                legacy_provenance=(
                    "platform_version" in payload or "source_commit" in payload
                ),
            )
        else:
            parts = line.split()
            if len(parts) != 2:
                raise ValueError(f"invalid lock entry at line {line_number}")

            digest, workflow = parts
            if not _valid_hex(digest, 32):
                raise ValueError(f"invalid MD5 at line {line_number}")
            entry = LockEntry(
                workflow=workflow,
                algorithm="md5",
                digest=digest,
            )

        if entry.workflow in entries:
            raise ValueError(f"duplicate lock entry: {entry.workflow}")
        entries[entry.workflow] = entry

    return entries


def parse_lock(path: Path) -> dict[str, str]:
    return {
        name: entry.digest
        for name, entry in parse_lock_records(path).items()
    }


def write_lock(
    path: Path,
    entries: dict[str, LockEntry | str],
) -> None:
    lines = [LOCK_HEADER.rstrip("\n"), ""]

    if entries and all(isinstance(value, str) for value in entries.values()):
        lines.extend(
            f"{entries[name]} {name}"
            for name in sorted(entries)
        )
    else:
        lines.extend([LOCK_SCHEMA_HEADER.rstrip("\n"), ""])
        for name in sorted(entries):
            value = entries[name]
            if isinstance(value, str):
                raise ValueError("cannot mix legacy and v2 lock entries")
            lines.append(value.to_json())

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def matches_source(entry: LockEntry, source_file: Path) -> bool:
    if entry.algorithm == "md5":
        return entry.digest == md5(source_file)
    if entry.algorithm == "sha256":
        return entry.digest == sha256(source_file)
    raise ValueError(f"unsupported lock digest algorithm: {entry.algorithm}")


def desired_entry(
    workflow: str,
    source_file: Path,
    *,
    catalog_commit: str,
) -> LockEntry:
    return LockEntry(
        workflow=workflow,
        algorithm="sha256",
        digest=sha256(source_file),
        catalog_commit=catalog_commit,
    )


def apply_patch(target_root: Path, target_file: Path) -> tuple[bool, str]:
    patch_file = Path(f"{target_file}.patch")
    if not patch_file.is_file():
        return True, ""

    relative_patch = patch_file.relative_to(target_root)
    result = subprocess.run(
        ["patch", "--batch", "--forward", "-p1"],
        cwd=target_root,
        input=patch_file.read_bytes(),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    output = result.stdout.decode("utf-8", errors="replace").strip()
    if result.returncode == 0:
        return True, f"Patch applied: {relative_patch}"

    return False, f"Patch failed: {relative_patch}\n{output}"


def render_expected(
    source_file: Path,
    target_root: Path,
    target_file: Path,
) -> tuple[bytes | None, bool, str]:
    patch_file = Path(f"{target_file}.patch")
    if not patch_file.is_file():
        return source_file.read_bytes(), True, ""

    with tempfile.TemporaryDirectory() as directory:
        candidate_root = Path(directory)
        candidate_file = candidate_root / ".github/workflows" / source_file.name
        candidate_file.parent.mkdir(parents=True)
        shutil.copyfile(source_file, candidate_file)
        shutil.copyfile(patch_file, Path(f"{candidate_file}.patch"))
        patch_ok, patch_message = apply_patch(candidate_root, candidate_file)
        if not patch_ok:
            return None, False, patch_message
        return candidate_file.read_bytes(), True, patch_message


def workflow_files(source: Path) -> list[Path]:
    return sorted(
        path
        for path in source.iterdir()
        if path.is_file() and path.suffix in {".yml", ".yaml"}
    )


def sync(
    source: Path,
    target: Path,
    lock_path: Path,
    *,
    catalog_commit: str = "",
) -> dict[str, object]:
    if not source.is_dir():
        raise ValueError(f"source directory does not exist: {source}")
    if not target.is_dir():
        raise ValueError(f"target directory does not exist: {target}")

    entries = parse_lock_records(lock_path)
    updated: list[str] = []
    adopted: list[str] = []
    unchanged: list[str] = []
    skipped: list[str] = []
    failed: list[str] = []
    diverged: list[str] = []
    provenance_updated: list[str] = []
    details: list[str] = []

    source_by_name = {path.name: path for path in workflow_files(source)}

    stale_entries = sorted(set(entries) - set(source_by_name))
    for name in stale_entries:
        del entries[name]

    for name in sorted(entries):
        if name in source_by_name:
            target_file = target / ".github/workflows" / name
            if not target_file.is_file():
                failed.append(name)
                diverged.append(name)
                details.append(
                    f"- {name}: managed workflow is missing from the consumer repository"
                )

    for name, source_file in source_by_name.items():
        target_file = target / ".github/workflows" / name

        if not target_file.is_file():
            if name not in entries:
                skipped.append(name)
            continue

        locked = entries.get(name)
        desired = desired_entry(
            name,
            source_file,
            catalog_commit=catalog_commit,
        )

        if locked is None:
            expected, patch_ok, patch_message = render_expected(
                source_file, target, target_file
            )
            if not patch_ok:
                failed.append(name)
                details.append(f"- {name}: {patch_message}")
                continue
            if target_file.read_bytes() != expected:
                failed.append(name)
                diverged.append(name)
                details.append(
                    f"- {name}: local workflow differs from catalog + local patch; "
                    "add or update a .patch file before adopting it"
                )
                continue

            entries[name] = desired
            adopted.append(name)
            if patch_message:
                details.append(f"- {name}: adopted; {patch_message}")
            continue

        if matches_source(locked, source_file):
            expected, patch_ok, patch_message = render_expected(
                source_file, target, target_file
            )
            if not patch_ok:
                failed.append(name)
                details.append(f"- {name}: {patch_message}")
                continue
            if target_file.read_bytes() != expected:
                failed.append(name)
                diverged.append(name)
                details.append(
                    f"- {name}: local workflow diverged from the locked catalog "
                    "version and local patch"
                )
                continue

            if locked != desired:
                entries[name] = desired
                provenance_updated.append(name)
                details.append(
                    f"- {name}: lock provenance migrated/updated without rewriting workflow"
                )
            else:
                unchanged.append(name)
            continue

        shutil.copyfile(source_file, target_file)
        patch_ok, patch_message = apply_patch(target, target_file)
        entries[name] = desired
        updated.append(name)

        if patch_message:
            details.append(f"- {name}: {patch_message}")
        if not patch_ok:
            failed.append(name)

    lock_changed = bool(
        updated or adopted or stale_entries or provenance_updated
    )
    if lock_changed:
        write_lock(lock_path, entries)

    return {
        "changed": lock_changed,
        "patch_failed": bool(set(failed) - set(diverged)),
        "blocked": bool(diverged),
        "updated": updated,
        "adopted": adopted,
        "unchanged": unchanged,
        "skipped": skipped,
        "failed": failed,
        "diverged": diverged,
        "provenance_updated": provenance_updated,
        "details": details,
        "removed_from_lock": stale_entries,
    }


def render_summary(report: dict[str, object]) -> str:
    lines = [
        "## Workflow synchronization",
        "",
        f"- Updated: {len(report['updated'])}",
        f"- Adopted: {len(report['adopted'])}",
        f"- Provenance updated: {len(report['provenance_updated'])}",
        f"- Unchanged: {len(report['unchanged'])}",
        f"- Skipped: {len(report['skipped'])}",
        f"- Failed: {len(report['failed'])}",
    ]

    details = report["details"]
    if details:
        lines.extend(["", "### Details", "", *details])

    lines.append("")
    return "\n".join(lines)


def write_output(name: str, value: str) -> None:
    output = os.environ.get("GITHUB_OUTPUT")
    if not output:
        return

    with Path(output).open("a", encoding="utf-8") as handle:
        if "\n" in value:
            delimiter = f"WORKFLOW_SYNC_{name.upper()}"
            handle.write(f"{name}<<{delimiter}\n{value}{delimiter}\n")
        else:
            handle.write(f"{name}={value}\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--lock-file", default=".github/actions-lock.txt")
    parser.add_argument("--catalog-commit", default="")
    args = parser.parse_args()

    try:
        source = args.source.resolve()
        target = args.target.resolve()
        lock_path = target / args.lock_file

        report = sync(
            source,
            target,
            lock_path,
            catalog_commit=args.catalog_commit,
        )

        summary = render_summary(report)
        summary_root = Path(os.environ.get("RUNNER_TEMP", target / ".github"))
        summary_path = summary_root / "workflow-sync-summary.md"
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(summary, encoding="utf-8")

        write_output("changed", str(report["changed"]).lower())
        write_output("patch_failed", str(report["patch_failed"]).lower())
        write_output("blocked", str(report["blocked"]).lower())
        write_output("updated", json.dumps(report["updated"], separators=(",", ":")))
        write_output("failed", json.dumps(report["failed"], separators=(",", ":")))
        write_output("summary", summary)
        write_output("summary_file", str(summary_path))

        print(json.dumps(report, indent=2, sort_keys=True))
        return 1 if report["blocked"] else 0
    except (OSError, ValueError) as error:
        parser.error(str(error))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
