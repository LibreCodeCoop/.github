#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 LibreCode Coop and contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Test a CI aggregate's explicit same-workflow `needs` result manifest.

Never use this script to declare a real GitHub required context without a
separately validated coordinator and check-run identity/revision contract.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

KNOWN = {"success", "failure", "cancelled", "skipped", "pending", "in_progress"}


def check_results(required: list[str], actual: dict[str, object], allowed_skips: set[str] | None = None) -> list[str]:
    if not required or len(required) != len(set(required)):
        raise ValueError("required jobs must be a nonempty, unique list")
    skips = allowed_skips or set()
    if skips - set(required):
        raise ValueError("allowed_skips must be a subset of required jobs")
    failures = []
    for job in required:
        record = actual.get(job)
        result = record.get("result") if isinstance(record, dict) else None
        if result not in KNOWN:
            failures.append(f"{job}: missing or unknown result")
        elif result == "success" or (result == "skipped" and job in skips):
            continue
        else:
            failures.append(f"{job}: {result}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True, help="JSON with required, needs and optional allowed_skips")
    args = parser.parse_args()
    try:
        payload = json.loads(args.manifest.read_text(encoding="utf-8"))
        failures = check_results(payload["required"], payload["needs"], set(payload.get("allowed_skips", [])))
    except (ValueError, KeyError, TypeError, OSError) as e:
        parser.error(str(e))
    if failures:
        for problem in failures:
            print("BLOCKED: " + problem)
        return 1
    print("Result manifest is consistent with explicit required jobs (not a remote CI certification).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
