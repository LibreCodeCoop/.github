# SPDX-FileCopyrightText: 2026 LibreCode coop and contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "actions" / "first-merged-pr-comment" / "first_merged_pr_comment.py"

spec = importlib.util.spec_from_file_location("first_merged_pr_comment", SCRIPT)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class FakeApi:
    def __init__(self, *, total_count: int = 0, comments: list[dict[str, Any]] | None = None) -> None:
        self.total_count = total_count
        self.comments = comments or []
        self.calls: list[tuple[str, str, dict[str, Any] | None]] = []

    def __call__(
        self,
        method: str,
        url: str,
        token: str,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        self.calls.append((method, url, payload))
        if "/search/issues?" in url:
            return {"total_count": self.total_count}
        if "/comments?" in url:
            return self.comments
        if method == "POST" and url.endswith("/comments"):
            return {"id": 123}
        raise AssertionError(f"unexpected API request: {method} {url}")


class FirstMergedPrCommentTest(unittest.TestCase):
    def setUp(self) -> None:
        self.pr = {
            "number": 42,
            "html_url": "https://git.example/acme/project/pull/42",
            "merged": True,
            "closed_at": "2026-09-23T12:00:00Z",
            "merge_commit_sha": "abc123",
            "user": {"login": "alice", "type": "User"},
        }

    def process(self, api: FakeApi, *, pr: dict[str, Any] | None = None, template: str = "Thanks {contributor_mention}") -> dict[str, str]:
        return module.process_pull_request(
            pr=pr or self.pr,
            repository="acme/project",
            token="token",
            api_url="https://git.example/api/v3",
            server_url="https://git.example",
            template=template,
            request=api,
        )

    def test_build_context_is_generic(self) -> None:
        context = module.build_context(
            pr=self.pr,
            repository="acme/project",
            server_url="https://git.example",
            api_url="https://git.example/api/v3",
        )
        self.assertEqual(context["server_url"], "https://git.example")
        self.assertEqual(context["api_url"], "https://git.example/api/v3")
        self.assertEqual(context["repository"], "acme/project")
        self.assertEqual(context["repository_owner"], "acme")
        self.assertEqual(context["repository_name"], "project")
        self.assertEqual(context["repository_url"], "https://git.example/acme/project")
        self.assertEqual(context["pull_request_number"], "42")
        self.assertEqual(context["pull_request_url"], "https://git.example/acme/project/pull/42")
        self.assertEqual(context["contributor_login"], "alice")
        self.assertEqual(context["contributor_mention"], "@alice")
        self.assertEqual(context["contributor_url"], "https://git.example/alice")
        self.assertEqual(context["merge_commit_sha"], "abc123")

    def test_render_template_composes_arbitrary_urls(self) -> None:
        context = module.build_context(
            pr=self.pr,
            repository="acme/project",
            server_url="https://git.example",
            api_url="https://git.example/api/v3",
        )
        rendered = module.render_template(
            "Hello {contributor_mention}. "
            "Docs: {repository_url}/docs. "
            "Feedback: https://forms.example/respond?repo={repository|urlencode}"
            "&user={contributor_login|urlencode}&pr={pull_request_number}.",
            context,
        )
        self.assertEqual(
            rendered,
            "Hello @alice. Docs: https://git.example/acme/project/docs. "
            "Feedback: https://forms.example/respond?repo=acme%2Fproject"
            "&user=alice&pr=42.",
        )

    def test_render_template_rejects_unknown_placeholder(self) -> None:
        with self.assertRaisesRegex(module.ActionError, "unknown placeholder: custom_url"):
            module.render_template("{custom_url}", {"repository": "acme/project"})

    def test_render_template_rejects_unknown_filter(self) -> None:
        with self.assertRaisesRegex(module.ActionError, "unknown placeholder filter: shell"):
            module.render_template("{repository|shell}", {"repository": "acme/project"})

    def test_render_template_rejects_empty_message(self) -> None:
        with self.assertRaisesRegex(module.ActionError, "message template is empty"):
            module.render_template("   ", {})

    def test_first_merged_pr_creates_comment(self) -> None:
        api = FakeApi()
        result = self.process(
            api,
            template=(
                "Thanks {contributor_mention}. "
                "{server_url}/{repository}/issues?author={contributor_login|urlencode}"
            ),
        )
        self.assertEqual(result["is-first-merged"], "true")
        self.assertEqual(result["comment-created"], "true")
        post = [call for call in api.calls if call[0] == "POST"]
        self.assertEqual(len(post), 1)
        self.assertIn(module.MARKER, post[0][2]["body"])
        self.assertIn("Thanks @alice.", post[0][2]["body"])

    def test_second_merged_pr_does_not_create_comment(self) -> None:
        api = FakeApi(total_count=1)
        result = self.process(api)
        self.assertEqual(result["is-first-merged"], "false")
        self.assertEqual(result["comment-created"], "false")
        self.assertFalse(any(call[0] == "POST" for call in api.calls))

    def test_closed_unmerged_pr_does_not_call_api(self) -> None:
        api = FakeApi()
        pr = dict(self.pr, merged=False)
        result = self.process(api, pr=pr)
        self.assertEqual(result["is-first-merged"], "false")
        self.assertEqual(result["comment-created"], "false")
        self.assertEqual(api.calls, [])

    def test_bot_pr_does_not_call_api(self) -> None:
        api = FakeApi()
        pr = dict(self.pr, user={"login": "renovate[bot]", "type": "Bot"})
        result = self.process(api, pr=pr)
        self.assertEqual(result["comment-created"], "false")
        self.assertEqual(api.calls, [])

    def test_existing_bot_marker_makes_retry_idempotent(self) -> None:
        api = FakeApi(
            comments=[
                {
                    "body": f"{module.MARKER}\nAlready sent",
                    "user": {"login": "github-actions[bot]", "type": "Bot"},
                }
            ]
        )
        result = self.process(api)
        self.assertEqual(result["is-first-merged"], "true")
        self.assertEqual(result["comment-created"], "false")
        self.assertFalse(any(call[0] == "POST" for call in api.calls))

    def test_user_cannot_suppress_comment_by_copying_marker(self) -> None:
        api = FakeApi(
            comments=[
                {
                    "body": f"{module.MARKER}\nSpoofed",
                    "user": {"login": "alice", "type": "User"},
                }
            ]
        )
        result = self.process(api)
        self.assertEqual(result["is-first-merged"], "true")
        self.assertEqual(result["comment-created"], "true")

    def test_previous_merged_query_excludes_current_pr(self) -> None:
        query = module.previous_merged_query(
            "acme/project",
            "alice",
            "2026-09-23T12:00:00Z",
        )
        self.assertEqual(
            query,
            "repo:acme/project is:pr is:merged author:alice "
            "closed:<2026-09-23T12:00:00Z",
        )

    def test_first_merge_does_not_depend_on_current_pr_search_indexing(self) -> None:
        api = FakeApi(total_count=0)
        result = self.process(api)
        self.assertEqual(result["is-first-merged"], "true")
        self.assertEqual(result["comment-created"], "true")

    def test_authorization_header_is_not_forwarded_on_redirects(self) -> None:
        request = module.build_api_request(
            "GET",
            "https://api.github.com/repos/acme/project",
            "secret-token",
        )
        self.assertNotIn("Authorization", request.headers)
        self.assertEqual(
            request.unredirected_hdrs["Authorization"],
            "Bearer secret-token",
        )

    def test_marker_is_stable_for_idempotency(self) -> None:
        self.assertEqual(
            module.MARKER,
            "<!-- librecode:first-merged-pr-comment -->",
        )

    def test_action_contract_has_no_product_specific_inputs(self) -> None:
        action = (
            ROOT / "actions" / "first-merged-pr-comment" / "action.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("message-template:", action)
        self.assertIn("pull-request-number:", action)
        self.assertNotIn("survey", action.lower())
        self.assertNotIn("community", action.lower())
        self.assertNotIn("good first issue", action.lower())

    def test_workflow_template_only_exposes_message_configuration(self) -> None:
        workflow = (
            ROOT / "workflow-templates" / "first-merged-pr-comment.yml"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "message-template: ${{ vars.FIRST_MERGED_PR_MESSAGE }}",
            workflow,
        )
        self.assertNotIn("env:\n      FIRST_MERGED_PR_MESSAGE", workflow)
        self.assertNotIn(
            "Thanks {contributor_mention}! Your first pull request",
            workflow,
        )
        self.assertNotIn("survey", workflow.lower())
        self.assertNotIn("community", workflow.lower())
        self.assertNotIn("good first issue", workflow.lower())
        self.assertNotIn("uses: actions/checkout@", workflow)


if __name__ == "__main__":
    unittest.main()
