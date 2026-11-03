<!-- SPDX-FileCopyrightText: 2026 LibreCode Coop and contributors -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# GitHub governance and workflow distribution

Sources: [governance configuration](https://github.com/LibreCodeCoop/.github/blob/main/governance.config.json), [repository governance](https://github.com/LibreCodeCoop/.github/blob/main/docs/repository-governance.md), [cross-repository automation](https://github.com/LibreCodeCoop/.github/blob/main/docs/cross-repository-automation.md), [dependency policy](https://github.com/LibreCodeCoop/.github/blob/main/docs/dependency-update-policy.md).

## Authority and rollout

- `LibreCodeCoop/.github` contains the organization configuration and the **workflow catalog**; the shared `github-governance` engine executes declarative synchronization. A merge to `.github` does not automatically apply a remote ruleset.
- `protected-branches` is declared active by default for eligible public, non-archived repos' default and `stable*` branches. It disallows deletion/force-push, requires one review, Code Owner review and resolved threads, and can dismiss stale approvals. Verify the **remote** ruleset and actual CODEOWNERS in each repo.
- `organization-config-ci` is active only for `.github` with required DCO/actionlint/zizmor. `governance-ci` is selected for `github-governance` with more checks. This is not evidence every consumer has those required contexts.
- `required-ci-gate` presently declares `enforcement: disabled`, selected only for `release-tool` and `nextcloud-docker-development`; it must not be enabled without producing/validating `ci-required` on those consumers.
- Ruleset sync: dry-run plan, human review of diff, protected environment authorization for explicit apply, remote verification, final drift check. This skill must never trigger apply automatically.

## CI aggregator correctness

1. List all *mandatory* jobs/check contexts, workflows, matrices and expected branch/ref; distinguish optional checks and allowed skips.
2. For jobs in one workflow, use a final `needs`-dependent job with `if: always()`; inspect every required `needs.<job>.result`. Treat `failure`, `cancelled`, `skipped` (unless an explicit and tested exemption), missing and unknown as blocking. The aggregate must not be successful because a dependency failed.
3. GitHub `needs` only reports jobs in the same workflow graph. Separate workflow runs need a tested coordinator that fetches correctly keyed check suites and handles not-yet-complete checks and reruns. Do not fake a green aggregate or depend on job presence alone.
4. Verify outcome on success, failure, cancellation, unexpected skip, rerun and fork PR; verify the context is attached to the SHA expected by branch protection. Test matrix failure and changes in mandatory job list.
5. Only after a real producer is stable may a separate authorized governance PR propose activation of required context. Do not modify governance config to accommodate a green placeholder.

`scripts/check_ci_results.py` is an offline contract-testing helper. It is **not** a GitHub Actions job, check publisher or substitute for cross-workflow coordination.

## Shared workflow adoption

1. Inspect `workflow-templates/` and selected language/application runtime. Use only applicable templates. The catalog contains `reuse`, commit lint, TypeScript, PHP/Nextcloud, Node, release and synchronization templates; it is not a generic Python/Go CI library.
2. Follow `docs/cross-repository-automation.md`: install workflows and optional `sync-workflow-templates.yml`, choose approved auth, run synchronization, review resulting PR. Track `.github/actions-lock.txt`. Place consumer-specific transformations in `.github/workflows/<name>.patch`; direct modifications to synced workflows will be treated as drift.
3. For selective enrollment, `include` must name an existing catalog workflow. Do not enroll all workflow templates blindly. Never assume sync is authorized to merge its own PR.
4. Templates derived from upstream use pinned manifest hash + downstream patch in the catalog; do not fork or edit the upstream copy independently. For local language-specific CI outside the catalog, document provenance and submit for architectural review before promotion.
5. New Actions `uses:` references require verified full 40-hex SHA and truthful adjacent upstream version comment; local `./` refs are exempt. For `actions/checkout`, set `persist-credentials: false`. Prefer explicit `permissions: contents: read`, scoped writes only for publishing jobs. Run `.github/scripts/check_workflow_policy.py` against consumer workflows or equivalent validated checker. Pin third-party containers by digest when feasible.

## PR/change policy

Never use `pull_request_target` to execute untrusted code with a write token. Privileged dependency automation verifies the bot actor, grants narrow permissions and does not approve arbitrary changes. Approved patch/minor auto-merge is separate from approval; **this skill never merges**. If adding CODEOWNERS, assign real consenting maintainers; organizational CODEOWNERS is not inherited by individual repositories. Avoid path filters that prevent a branch-required check from appearing on applicable PRs.
