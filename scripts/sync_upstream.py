#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 LibreCode coop and contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class Source:
    name: str
    url: str
    sha256: str
    destination: Path
    repository: str | None = None
    ref: str | None = None
    path: str | None = None


def load_sources(manifest_path: Path) -> list[Source]:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("manifest must be a JSON object")

    raw_sources = payload.get("sources")
    if not isinstance(raw_sources, list):
        raise ValueError("manifest.sources must be an array")

    sources: list[Source] = []
    for index, raw in enumerate(raw_sources):
        if not isinstance(raw, dict):
            raise ValueError(f"manifest.sources[{index}] must be an object")

        name = _non_empty_string(raw.get("name"), f"sources[{index}].name")
        url = _non_empty_string(raw.get("url"), f"sources[{index}].url")
        digest = _non_empty_string(raw.get("sha256"), f"sources[{index}].sha256")
        destination = _non_empty_string(
            raw.get("destination"), f"sources[{index}].destination"
        )

        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise ValueError(f"sources[{index}].sha256 must be 64 lowercase hex characters")
        _validate_immutable_url(url, f"sources[{index}].url")

        repository = _optional_string(raw.get("repository"), f"sources[{index}].repository")
        ref = _optional_string(raw.get("ref"), f"sources[{index}].ref")
        path = _optional_string(raw.get("path"), f"sources[{index}].path")
        tracking = (repository, ref, path)
        if any(value is not None for value in tracking) and not all(
            value is not None for value in tracking
        ):
            raise ValueError(
                f"sources[{index}] must define repository, ref and path together"
            )

        sources.append(
            Source(
                name=name,
                url=url,
                sha256=digest,
                destination=Path(destination),
                repository=repository,
                ref=ref,
                path=path,
            )
        )

    return sources


def fetch(source: Source) -> bytes:
    content = _download(source.url)
    actual = hashlib.sha256(content).hexdigest()
    if actual != source.sha256:
        raise ValueError(
            f"{source.name}: SHA-256 mismatch: expected {source.sha256}, got {actual}"
        )
    return content


def sync(sources: list[Source], root: Path) -> None:
    for source in sources:
        content = fetch(source)
        destination = _safe_destination(root, source.destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)


def check(sources: list[Source], root: Path) -> None:
    drift: list[str] = []
    for source in sources:
        expected = fetch(source)
        destination = _safe_destination(root, source.destination)
        if not destination.exists() or destination.read_bytes() != expected:
            drift.append(source.name)

    if drift:
        raise ValueError("generated templates are out of date: " + ", ".join(drift))


def refresh(manifest_path: Path, root: Path, token: str | None = None) -> None:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    raw_sources = payload.get("sources")
    if not isinstance(raw_sources, list):
        raise ValueError("manifest.sources must be an array")

    # Validate the current manifest before mutating it.
    load_sources(manifest_path)

    for index, raw in enumerate(raw_sources):
        if not isinstance(raw, dict):
            raise ValueError(f"manifest.sources[{index}] must be an object")

        repository = raw.get("repository")
        ref = raw.get("ref")
        path = raw.get("path")
        if not all(isinstance(value, str) and value for value in (repository, ref, path)):
            continue

        commit = _latest_commit(repository, ref, path, token)
        url = f"https://raw.githubusercontent.com/{repository}/{commit}/{path}"
        content = _download(url)
        digest = hashlib.sha256(content).hexdigest()

        if digest != raw["sha256"]:
            raw["url"] = url
            raw["sha256"] = digest

        destination = _safe_destination(root, Path(str(raw["destination"])))
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)

    manifest_path.write_text(
        json.dumps(payload, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )


def _latest_commit(repository: str, ref: str, path: str, token: str | None) -> str:
    url = (
        f"https://api.github.com/repos/{repository}/commits"
        f"?sha={quote(ref, safe='')}&path={quote(path, safe='')}&per_page=1"
    )
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "github-workflows-sync",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = Request(url, headers=headers)
    with urlopen(request, timeout=30) as response:
        payload = json.load(response)

    if not isinstance(payload, list) or not payload:
        raise ValueError(
            f"cannot resolve latest commit for {repository}:{ref}:{path}"
        )
    commit = payload[0].get("sha")
    if not isinstance(commit, str) or len(commit) != 40:
        raise ValueError(
            f"invalid commit returned for {repository}:{ref}:{path}"
        )
    return commit


def _download(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "github-workflows-sync"})
    with urlopen(request, timeout=30) as response:
        return response.read()


def _validate_immutable_url(url: str, path: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ValueError(f"{path} must use https")

    if parsed.hostname == "raw.githubusercontent.com":
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) < 4:
            raise ValueError(f"{path} is not a valid raw GitHub file URL")
        revision = parts[2]
        if len(revision) != 40 or any(
            char not in "0123456789abcdefABCDEF" for char in revision
        ):
            raise ValueError(f"{path} must pin a 40-character Git commit SHA")
    elif "/refs/heads/" in parsed.path:
        raise ValueError(f"{path} must not reference a mutable branch")


def _safe_destination(root: Path, destination: Path) -> Path:
    if destination.is_absolute() or ".." in destination.parts:
        raise ValueError(f"unsafe destination: {destination}")
    resolved = (root / destination).resolve()
    root_resolved = root.resolve()
    if resolved != root_resolved and root_resolved not in resolved.parents:
        raise ValueError(f"destination escapes repository root: {destination}")
    return resolved


def _non_empty_string(value: object, path: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{path} must be a non-empty string")
    return value


def _optional_string(value: object, path: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ValueError(f"{path} must be a non-empty string when defined")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("sync", "check", "refresh"))
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()

    root = Path.cwd()

    try:
        if args.command == "refresh":
            refresh(
                args.manifest,
                root,
                token=os.environ.get("GITHUB_TOKEN"),
            )
        else:
            sources = load_sources(args.manifest)
            if args.command == "sync":
                sync(sources, root)
            else:
                check(sources, root)
    except ValueError as error:
        parser.error(str(error))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
