#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 LibreCode coop and contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import argparse
import re
from pathlib import Path

USES_RE = re.compile(r"^\s*(?:-\s*)?uses:\s*([^@\s]+)@([^\s#]+)")
FULL_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")


def workflow_files(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix in {".yml", ".yaml"}
    )


def check_file(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    findings: list[str] = []

    for index, line in enumerate(lines):
        line_number = index + 1

        if re.search(r"permissions:\s*write-all\b", line):
            findings.append(f"{path}:{line_number}: permissions: write-all is forbidden")

        match = USES_RE.match(line)
        if not match:
            continue

        action, revision = match.groups()
        if action.startswith("./"):
            continue

        if not FULL_SHA_RE.fullmatch(revision):
            findings.append(
                f"{path}:{line_number}: {action} must be pinned to a full 40-character commit SHA"
            )

        if action == "actions/checkout":
            block = "\n".join(lines[index + 1 : index + 8])
            if not re.search(r"persist-credentials:\s*false\b", block):
                findings.append(
                    f"{path}:{line_number}: actions/checkout must set persist-credentials: false"
                )

    return findings


def check_roots(roots: list[Path]) -> list[str]:
    findings: list[str] = []
    for root in roots:
        if not root.exists():
            continue
        for path in workflow_files(root):
            findings.extend(check_file(path))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "roots",
        nargs="*",
        type=Path,
        default=[Path("workflow-templates"), Path(".github/workflows")],
    )
    args = parser.parse_args()

    findings = check_roots(args.roots)
    if findings:
        print("\n".join(findings))
        return 1

    print("Workflow policy checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
