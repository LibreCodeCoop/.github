#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 LibreCode Coop and contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Read-only, conservative inventory of a project's observable local controls.

A local audit cannot certify GitHub-side rulesets, approvals, action signing,
remote checks, dependency vulnerabilities or actual unit-test quality.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

FULL_SHA = re.compile(r"^[0-9a-fA-F]{40}$")
USE = re.compile(r"^\s*(?:-\s*)?uses:\s*([^@\s]+)@([^\s#]+)(.*)$")
VERSION = re.compile(r"^#\s*v?\d+(?:\.\d+){0,2}(?:[-.][A-Za-z0-9.-]+)?\s*$")


@dataclass
class Finding:
    id: str
    severity: str
    status: str
    evidence: str
    message: str


def inspect_workflow(path: Path, root: Path) -> list[Finding]:
    findings = []
    lines = path.read_text(encoding="utf-8").splitlines()
    rel = str(path.relative_to(root))
    for i, line in enumerate(lines):
        if re.search(r"permissions:\s*write-all\b", line):
            findings.append(Finding("workflow-least-privilege", "required", "FAIL", f"{rel}:{i+1}", "write-all is forbidden"))
        match = USE.match(line)
        if not match:
            continue
        action, revision, trailing = match.groups()
        if action.startswith("./"):
            continue
        if not FULL_SHA.fullmatch(revision):
            findings.append(Finding("workflow-immutable-uses", "required", "FAIL", f"{rel}:{i+1}", f"mutable or short revision: {action}@{revision}"))
            continue
        comment = trailing.strip()
        if action.startswith(("LibreCodeCoop/", "LibreSign/")):
            annotated = bool(re.fullmatch(r"#\s*\S(?:.*\S)?", comment))
        else:
            annotated = bool(VERSION.fullmatch(comment))
        if not annotated:
            findings.append(Finding("workflow-version-comment", "required", "FAIL", f"{rel}:{i+1}", "missing truthful upstream version/source comment"))
        if action == "actions/checkout":
            block = "\n".join(lines[i+1:i+8])
            if not re.search(r"persist-credentials:\s*false\b", block):
                findings.append(Finding("checkout-credentials", "required", "FAIL", f"{rel}:{i+1}", "checkout does not set persist-credentials: false"))
    return findings


def evaluate(root: Path) -> dict[str, object]:
    if not root.is_dir():
        raise ValueError(f"not a directory: {root}")
    f: list[Finding] = []

    def record(id: str, severity: str, status: str, path: str, message: str) -> None:
        f.append(Finding(id, severity, status, path, message))

    files = {p.name for p in root.iterdir() if p.is_file()}
    language = []
    for identifier, path in (("php", "composer.json"), ("python", "pyproject.toml"), ("javascript/typescript", "package.json"), ("go", "go.mod")):
        if path in files:
            language.append(identifier)
    record("language-manifest", "conditional", "PASS" if language else "UNKNOWN", ", ".join(language), "detected manifest(s); verify the declared runtime and lockfile")
    for required in ("README.md", "CONTRIBUTING.md"):
        record("document-" + required.lower(), "recommended", "PASS" if required in files else "UNKNOWN", required, "presence does not prove content adequacy" if required in files else "not found locally")
    if (root / "SECURITY.md").exists():
        record("security-reporting", "conditional", "PASS", "SECURITY.md", "reporting policy exists; verify private route is real")
    else:
        record("security-reporting", "conditional", "UNKNOWN", "SECURITY.md", "decide based on exposure and reporting needs")
    license_files = list((root / "LICENSES").glob("*")) if (root / "LICENSES").exists() else []
    record("full-license-text", "required", "PASS" if license_files else "UNKNOWN", "LICENSES/", "verify canonical license content and SPDX mapping" if license_files else "no REUSE license texts found")
    record("reuse-attribution", "recommended", "PASS" if (root / "REUSE.toml").exists() else "UNKNOWN", "REUSE.toml", "run external reuse lint; attribution not proven")
    owner = [str(p.relative_to(root)) for p in [root / ".github/CODEOWNERS", root / "CODEOWNERS", root / "docs/CODEOWNERS"] if p.is_file()]
    record("effective-codeowners", "conditional", "UNKNOWN", ", ".join(owner), "CODEOWNERS exists but reviewer coverage/remote enforcement must be verified" if owner else "no local CODEOWNERS found; repository review policy needs verification")
    test_dirs = [p for p in (root / "tests", root / "test", root / "spec") if p.exists()]
    record("unit-tests", "recommended", "UNKNOWN", ", ".join(str(p.relative_to(root)) for p in test_dirs), "tests found but execution/assertion quality unknown" if test_dirs else "tests directory not found; investigate language conventions")

    workflows_dir = root / ".github/workflows"
    workflows = sorted([p for p in workflows_dir.glob("*.yml") if p.is_file()] + [p for p in workflows_dir.glob("*.yaml") if p.is_file()]) if workflows_dir.is_dir() else []
    if not workflows:
        record("ci-producer", "conditional", "UNKNOWN", ".github/workflows/", "no local GitHub Actions producer found; verify externally required workflows and PR checks")
    else:
        for wf in workflows:
            f.extend(inspect_workflow(wf, root))
        record("ci-producer", "conditional", "UNKNOWN", ".github/workflows/", f"{len(workflows)} local workflow(s); execution, mandatory status and scoped permissions unverified")
    record("remote-governance", "required", "UNKNOWN", "GitHub rulesets/checks", "remote branch protection, DCO, CODEOWNERS approval, signatures and check SHA require GitHub inspection")
    record("ci-required-integrity", "conditional", "UNKNOWN", "GitHub check suites", "if ci-required is enabled, test required job coverage, failure, cancellation, skip, rerun and SHA; never assume aggregate correctness")
    record("dependency-supply-chain", "conditional", "UNKNOWN", "package manifests and CI", "locked installation and vulnerability scans not run by read-only auditor")
    record("runtime-verification", "required", "UNKNOWN", "test/analysis commands", "execute language-native checks and record exit codes separately")
    return {"project": str(root), "languages": language, "certification": "NOT_CERTIFIED", "findings": [asdict(x) for x in f], "summary": {status: sum(x.status == status for x in f) for status in ("PASS", "FAIL", "UNKNOWN")}}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    parser.add_argument("--strict", action="store_true", help="nonzero if definite local policy violations were detected")
    args = parser.parse_args()
    try:
        report = evaluate(args.project.expanduser().resolve())
    except (ValueError, OSError) as e:
        parser.error(str(e))
    print(json.dumps(report, indent=2))
    return int(args.strict and report["summary"]["FAIL"] > 0)


if __name__ == "__main__":
    raise SystemExit(main())
