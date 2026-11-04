#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 LibreCode coop and contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Find safe public-repository candidates for baseline-only governance onboarding.

Discovery is read-only. The privileged onboarding action must still verify
classic protection and all rulesets immediately before creating any rule.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

REPOSITORY_NAME = re.compile(r"[A-Za-z0-9_.-]+")
MAX_MATRIX_SIZE = 200


class GitHubAPI:
    def __init__(self, token: str, base_url: str = "https://api.github.com") -> None:
        if not token:
            raise ValueError("GitHub read-only token is required")
        self._token = token
        self._base_url = base_url.rstrip("/")

    def get(self, path: str) -> object:
        request = Request(
            f"{self._base_url}{path}",
            headers={
                "Authorization": f"Bearer {self._token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "librecode-governance-onboarding",
            },
        )
        with urlopen(request, timeout=20) as response:
            return json.load(response)

    def list_public_repositories(self, organization: str) -> list[dict[str, object]]:
        repositories: list[dict[str, object]] = []
        page = 1
        while True:
            query = urlencode({"type": "public", "per_page": 100, "page": page})
            result = self.get(f"/orgs/{quote(organization, safe='')}/repos?{query}")
            if not isinstance(result, list):
                raise ValueError("Unexpected GitHub repository listing")
            repositories.extend(result)
            if len(result) < 100:
                return repositories
            page += 1

    def rulesets(self, organization: str, repository: str) -> list[object]:
        result = self.get(
            f"/repos/{quote(organization, safe='')}/{quote(repository, safe='')}"
            "/rulesets?includes_parents=true"
        )
        if not isinstance(result, list):
            raise ValueError(f"Unexpected GitHub rulesets response for {repository}")
        return result

    def branch_exists(self, organization: str, repository: str, branch: str) -> bool:
        path = (
            f"/repos/{quote(organization, safe='')}/{quote(repository, safe='')}"
            f"/branches/{quote(branch, safe='')}"
        )
        try:
            self.get(path)
        except HTTPError as error:
            if error.code == 404:
                return False
            raise
        return True


@dataclass(frozen=True)
class Discovery:
    candidates: list[str]
    exceptions: list[str]
    uninitialized: list[str]


def discover(api: GitHubAPI, organization: str) -> Discovery:
    candidates: list[str] = []
    exceptions: list[str] = []
    uninitialized: list[str] = []
    for repo in api.list_public_repositories(organization):
        if not isinstance(repo, dict):
            raise ValueError("Unexpected repository metadata")
        if repo.get("archived") or repo.get("private") or repo.get("visibility") != "public":
            continue
        owner = repo.get("owner")
        if not isinstance(owner, dict) or owner.get("login") != organization:
            raise ValueError("Unexpected repository owner in GitHub response")
        name = repo.get("name")
        if not isinstance(name, str) or not REPOSITORY_NAME.fullmatch(name):
            raise ValueError(f"Invalid GitHub repository name: {name!r}")
        branch = repo.get("default_branch")
        if not isinstance(branch, str) or not branch:
            uninitialized.append(name)
            continue
        # Existing rulesets (including custom ones) are explicit exceptions:
        # never auto-modify these repositories, even if the common rule differs.
        if api.rulesets(organization, name):
            exceptions.append(name)
            continue
        if not api.branch_exists(organization, name, branch):
            uninitialized.append(name)
            continue
        candidates.append(name)
    candidates.sort()
    if len(candidates) > MAX_MATRIX_SIZE:
        raise ValueError("Too many candidates for one GitHub Actions matrix; review required")
    return Discovery(candidates, sorted(exceptions), sorted(uninitialized))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--organization", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.organization != "LibreCodeCoop":
        parser.error("This caller may only manage LibreCodeCoop")
    try:
        result = discover(GitHubAPI(os.environ.get("GH_TOKEN", "")), args.organization)
    except (HTTPError, OSError, ValueError) as error:
        print(f"::error::Read-only onboarding discovery failed: {error}", file=sys.stderr)
        return 1

    payload = json.dumps(result.candidates, separators=(",", ":"))
    with args.output.open("a", encoding="utf-8") as output:
        output.write(f"repositories={payload}\n")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with Path(summary).open("a", encoding="utf-8") as output:
            output.write(
                "## Automatic baseline protection discovery\n\n"
                f"- Missing protection candidates: {len(result.candidates)}\n"
                f"- Existing custom/institutional rulesets left untouched: {len(result.exceptions)}\n"
                f"- Not initialized: {len(result.uninitialized)}\n"
                "- Each candidate is rechecked by the privileged engine before mutation.\n"
            )
    print(
        f"Candidates: {len(result.candidates)}; "
        f"existing rulesets: {len(result.exceptions)}; "
        f"uninitialized: {len(result.uninitialized)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
