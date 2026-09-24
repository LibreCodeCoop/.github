#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 LibreCode coop and contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Template:
    name: str
    source: Path
    patches: tuple[Path, ...]
    destination: Path


def load_templates(manifest_path: Path) -> list[Template]:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("manifest must be a JSON object")

    raw_templates = payload.get("templates")
    if not isinstance(raw_templates, list):
        raise ValueError("manifest.templates must be an array")

    templates: list[Template] = []
    for index, raw in enumerate(raw_templates):
        if not isinstance(raw, dict):
            raise ValueError(f"manifest.templates[{index}] must be an object")

        name = _non_empty_string(raw.get("name"), f"templates[{index}].name")
        source = Path(_non_empty_string(raw.get("source"), f"templates[{index}].source"))
        destination = Path(
            _non_empty_string(raw.get("destination"), f"templates[{index}].destination")
        )

        raw_patches = raw.get("patches", [])
        if not isinstance(raw_patches, list) or not all(
            isinstance(item, str) and item for item in raw_patches
        ):
            raise ValueError(f"templates[{index}].patches must be an array of paths")

        for path in (source, destination, *(Path(item) for item in raw_patches)):
            _validate_relative_path(path)

        templates.append(
            Template(
                name=name,
                source=source,
                patches=tuple(Path(item) for item in raw_patches),
                destination=destination,
            )
        )

    return templates


def render(template: Template, root: Path) -> bytes:
    source = _safe_path(root, template.source)
    if not source.is_file():
        raise ValueError(f"source does not exist: {template.source}")

    with tempfile.TemporaryDirectory() as directory:
        working = Path(directory) / source.name
        shutil.copyfile(source, working)

        for patch_path in template.patches:
            patch = _safe_path(root, patch_path)
            if not patch.is_file():
                raise ValueError(f"patch does not exist: {patch_path}")

            result = subprocess.run(
                ["patch", "--batch", "--forward", str(working), str(patch)],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                details = (result.stderr or result.stdout).strip()
                raise ValueError(f"failed to apply {patch_path}: {details}")

        return working.read_bytes()


def sync(templates: list[Template], root: Path) -> dict[str, object]:
    results: list[dict[str, object]] = []

    for template in templates:
        destination = _safe_path(root, template.destination)
        try:
            content = render(template, root)
            previous = destination.read_bytes() if destination.is_file() else None
            changed = previous != content
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)
            results.append(
                {
                    "name": template.name,
                    "status": "updated" if changed else "unchanged",
                    "destination": str(template.destination),
                    "patches": [str(path) for path in template.patches],
                }
            )
        except ValueError as error:
            results.append(
                {
                    "name": template.name,
                    "status": "failed",
                    "destination": str(template.destination),
                    "patches": [str(path) for path in template.patches],
                    "error": str(error),
                }
            )

    counts = {
        status: sum(1 for item in results if item["status"] == status)
        for status in ("updated", "unchanged", "failed")
    }
    return {
        "ok": counts["failed"] == 0,
        **counts,
        "templates": results,
    }


def check(templates: list[Template], root: Path) -> None:
    problems: list[str] = []
    for template in templates:
        try:
            expected = render(template, root)
        except ValueError as error:
            problems.append(f"{template.name}: {error}")
            continue

        destination = _safe_path(root, template.destination)
        if not destination.is_file() or destination.read_bytes() != expected:
            problems.append(f"{template.name}: rendered template is out of date")

    if problems:
        raise ValueError("; ".join(problems))


def write_report(report: dict[str, object], path: Path) -> None:
    path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def render_pull_request_body(report: dict[str, object] | None) -> str:
    lines = [
        "Automated refresh of tracked upstream workflow sources.",
        "",
        "The source URLs in this change are pinned to immutable commit SHAs "
        "and SHA-256 hashes.",
        "",
        "## Patch status",
        "",
    ]

    if report is None:
        lines.append("No patch report was produced. Review the workflow run before merging.")
    else:
        lines.extend(
            [
                f"- Updated templates: {report['updated']}",
                f"- Unchanged templates: {report['unchanged']}",
                f"- Failed templates: {report['failed']}",
                "",
            ]
        )

        for item in report["templates"]:
            status = item["status"]
            icon = {"updated": "✅", "unchanged": "➖", "failed": "❌"}[status]
            lines.append(f"### {icon} {item['name']} — {status}")
            lines.append("")
            lines.append(f"Destination: {item['destination']}")

            patches = item["patches"]
            if patches:
                lines.extend(["", "Patches:"])
                lines.extend(f"- {patch}" for patch in patches)

            if status == "failed":
                lines.extend(
                    [
                        "",
                        "Patch application failed:",
                        "",
                        "~~~text",
                        str(item["error"]),
                        "~~~",
                        "",
                        "The vendored upstream source was updated, but the generated "
                        "template was left unchanged and needs manual patch adjustment.",
                    ]
                )

            lines.append("")

    lines.extend(
        [
            "Review upstream changes and downstream patches before merging.",
            "",
        ]
    )
    return "\n".join(lines)


def write_pull_request_body(report_path: Path, output_path: Path) -> None:
    report = None
    if report_path.is_file():
        report = json.loads(report_path.read_text(encoding="utf-8"))
    output_path.write_text(render_pull_request_body(report), encoding="utf-8")


def _validate_relative_path(path: Path) -> None:
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"unsafe path: {path}")


def _safe_path(root: Path, path: Path) -> Path:
    _validate_relative_path(path)
    resolved = (root / path).resolve()
    root_resolved = root.resolve()
    if resolved != root_resolved and root_resolved not in resolved.parents:
        raise ValueError(f"path escapes repository root: {path}")
    return resolved


def _non_empty_string(value: object, path: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{path} must be a non-empty string")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("sync", "check", "pr-body"))
    parser.add_argument("manifest", type=Path, nargs="?")
    parser.add_argument("--report", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    root = Path.cwd()

    try:
        if args.command == "pr-body":
            if args.report is None or args.output is None:
                parser.error("pr-body requires --report and --output")
            write_pull_request_body(args.report, args.output)
            return 0

        if args.manifest is None:
            parser.error(f"{args.command} requires a manifest")

        templates = load_templates(args.manifest)
        if args.command == "sync":
            report = sync(templates, root)
            if args.report:
                write_report(report, args.report)
            print(json.dumps(report, indent=2, sort_keys=True))
            return 0 if report["ok"] else 1

        check(templates, root)
    except (OSError, ValueError) as error:
        parser.error(str(error))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
