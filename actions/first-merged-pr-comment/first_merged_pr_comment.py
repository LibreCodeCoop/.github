#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 LibreCode coop and contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable

MARKER = "<!-- librecode:first-merged-pr-comment -->"
PLACEHOLDER = re.compile(r"\{([a-z][a-z0-9_]*)(?:\|([a-z][a-z0-9_]*))?\}")
ALLOWED_FILTERS = {"urlencode"}
ApiRequest = Callable[[str, str, str, dict[str, Any] | None], Any]


class ActionError(RuntimeError):
    pass


def render_template(template: str, context: dict[str, str]) -> str:
    if not template.strip():
        raise ActionError("message template is empty")

    def replace(match: re.Match[str]) -> str:
        name, filter_name = match.groups()
        if name not in context:
            raise ActionError(f"unknown placeholder: {name}")
        value = context[name]
        if filter_name is None:
            return value
        if filter_name not in ALLOWED_FILTERS:
            raise ActionError(f"unknown placeholder filter: {filter_name}")
        return urllib.parse.quote(value, safe="")

    return PLACEHOLDER.sub(replace, template)


def build_context(
    *,
    pr: dict[str, Any],
    repository: str,
    server_url: str,
    api_url: str,
) -> dict[str, str]:
    owner, repository_name = repository.split("/", 1)
    login = str(pr["user"]["login"])
    number = str(pr["number"])
    clean_server_url = server_url.rstrip("/")
    return {
        "server_url": clean_server_url,
        "api_url": api_url.rstrip("/"),
        "repository": repository,
        "repository_owner": owner,
        "repository_name": repository_name,
        "repository_url": f"{clean_server_url}/{repository}",
        "pull_request_number": number,
        "pull_request_url": str(
            pr.get("html_url")
            or f"{clean_server_url}/{repository}/pull/{number}"
        ),
        "contributor_login": login,
        "contributor_mention": f"@{login}",
        "contributor_url": f"{clean_server_url}/{login}",
        "merge_commit_sha": str(pr.get("merge_commit_sha") or ""),
    }


def build_api_request(
    method: str,
    url: str,
    token: str,
    payload: dict[str, Any] | None = None,
) -> urllib.request.Request:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    # Keep credentials off redirected requests. urllib forwards normal headers
    # across redirects, which could otherwise disclose the GitHub token if an
    # API endpoint ever redirected to a different origin.
    request.add_unredirected_header("Authorization", f"Bearer {token}")
    return request


def api_request(
    method: str,
    url: str,
    token: str,
    payload: dict[str, Any] | None = None,
) -> Any:
    request = build_api_request(method, url, token, payload)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise ActionError(f"GitHub API request failed ({error.code}): {body}") from error
    return json.loads(body) if body else None


def pull_request_from_event(event_path: str) -> dict[str, Any] | None:
    if not event_path:
        return None
    payload = json.loads(Path(event_path).read_text(encoding="utf-8"))
    pr = payload.get("pull_request")
    return pr if isinstance(pr, dict) else None


def write_output(name: str, value: str) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if not path:
        return
    with Path(path).open("a", encoding="utf-8") as handle:
        handle.write(f"{name}={value}\n")


def previous_merged_query(repository: str, login: str, closed_at: str) -> str:
    return " ".join(
        (
            f"repo:{repository}",
            "is:pr",
            "is:merged",
            f"author:{login}",
            f"closed:<{closed_at}",
        )
    )


def has_action_marker_comment(
    *,
    api_url: str,
    repository: str,
    pull_request_number: int,
    token: str,
    request: ApiRequest = api_request,
) -> bool:
    owner, repo = repository.split("/", 1)
    page = 1
    while True:
        batch = request(
            "GET",
            f"{api_url}/repos/{owner}/{repo}/issues/{pull_request_number}/comments"
            f"?per_page=100&page={page}",
            token,
            None,
        )
        for comment in batch:
            author = comment.get("user") or {}
            if (
                author.get("type") == "Bot"
                and MARKER in str(comment.get("body") or "")
            ):
                return True
        if len(batch) < 100:
            return False
        page += 1


def process_pull_request(
    *,
    pr: dict[str, Any],
    repository: str,
    token: str,
    api_url: str,
    server_url: str,
    template: str,
    request: ApiRequest = api_request,
) -> dict[str, str]:
    result = {
        "is-first-merged": "false",
        "comment-created": "false",
        "contributor-login": str(pr["user"]["login"]),
        "pull-request-number": str(pr["number"]),
    }

    if not pr.get("merged") or pr.get("user", {}).get("type") == "Bot":
        return result

    login = str(pr["user"]["login"])
    query = previous_merged_query(repository, login, str(pr["closed_at"]))
    encoded_query = urllib.parse.urlencode({"q": query, "per_page": 1})
    search = request(
        "GET",
        f"{api_url}/search/issues?{encoded_query}",
        token,
        None,
    )
    # Search only for earlier merged PRs. Do not require the current PR to
    # have reached the search index yet; the closed event can arrive before
    # search indexing catches up.
    if int(search["total_count"]) != 0:
        return result

    result["is-first-merged"] = "true"

    if has_action_marker_comment(
        api_url=api_url,
        repository=repository,
        pull_request_number=int(pr["number"]),
        token=token,
        request=request,
    ):
        return result

    context = build_context(
        pr=pr,
        repository=repository,
        server_url=server_url,
        api_url=api_url,
    )
    message = render_template(template, context).strip()

    owner, repo = repository.split("/", 1)
    request(
        "POST",
        f"{api_url}/repos/{owner}/{repo}/issues/{pr['number']}/comments",
        token,
        {"body": f"{MARKER}\n{message}"},
    )
    result["comment-created"] = "true"
    return result


def main() -> int:
    token = os.environ.get("FIRST_MERGED_PR_GITHUB_TOKEN", "")
    template = os.environ.get("FIRST_MERGED_PR_MESSAGE_TEMPLATE", "")
    manual_number = os.environ.get("FIRST_MERGED_PR_NUMBER", "").strip()
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    api_url = os.environ.get("GITHUB_API_URL", "https://api.github.com").rstrip("/")
    server_url = os.environ.get("GITHUB_SERVER_URL", "https://github.com").rstrip("/")

    if not token:
        raise ActionError("github token is required")
    if "/" not in repository:
        raise ActionError("GITHUB_REPOSITORY must be in owner/name form")

    pr = pull_request_from_event(os.environ.get("GITHUB_EVENT_PATH", ""))
    if pr is None:
        if not manual_number.isdigit() or int(manual_number) <= 0:
            raise ActionError("a valid pull-request-number is required for a manual run")
        owner, repo = repository.split("/", 1)
        pr = api_request(
            "GET",
            f"{api_url}/repos/{owner}/{repo}/pulls/{int(manual_number)}",
            token,
        )

    result = process_pull_request(
        pr=pr,
        repository=repository,
        token=token,
        api_url=api_url,
        server_url=server_url,
        template=template,
    )
    for name, value in result.items():
        write_output(name, value)

    if result["comment-created"] == "true":
        print(
            f"Created first-merged contribution comment on "
            f"PR #{result['pull-request-number']}."
        )
    elif result["is-first-merged"] == "true":
        print(
            f"PR #{result['pull-request-number']} already has a "
            "first-merged contribution comment; skipping."
        )
    else:
        print(
            f"PR #{result['pull-request-number']} is not the contributor's "
            "first merged pull request; skipping."
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ActionError, KeyError, OSError, ValueError, json.JSONDecodeError) as error:
        print(f"::error::{error}")
        raise SystemExit(1) from error
