<!--
SPDX-FileCopyrightText: 2026 LibreCode coop and contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Repository governance and CI

LibreCode Coop manages GitHub repository policies declaratively in
[`governance.config.json`](../governance.config.json). The shared
[`github-governance` engine](https://github.com/LibreCodeCoop/github-governance)
discovers public, non-archived repositories and reconciles repository-level
rulesets. Organization-specific settings remain in this repository; the
engine does not duplicate product or organization policy.

The workflow template catalog is a separate mechanism. See
[cross-repository automation](cross-repository-automation.md) for how
consumers opt in to shared workflows through reviewable pull requests.

## Policies and repository scope

- `protected-branches` applies by default to eligible public repositories
  on their default and `stable*` branches. It requires reviews, Code Owner
  approval and resolved review conversations, and prevents deletion and
  non-fast-forward updates.
- `governance-ci` is selected for `LibreCodeCoop/github-governance`; its
  required contexts include DCO, actionlint, REUSE, TypeScript, Vitest,
  zizmor and CodeQL.
- `organization-config-ci` is selected for `LibreCodeCoop/.github`
  and requires DCO, actionlint and zizmor.
- `required-ci-gate` is selected for both `LibreCodeCoop/release-tool` and
  `LibreCodeCoop/nextcloud-docker-development`, on their default branches
  only. It requires one stable context named `ci-required`. Its desired
  enforcement remains **disabled** until each consumer produces and verifies
  that aggregate check.

The configuration expresses desired policy, not proof that a ruleset was
already applied on GitHub. An organization-wide rollout is not automatic:
the consumer must have the matching check before protection is enabled.
Other repositories and stable branches are outside this initial CI gate.

## Contract for `ci-required`

Each consuming repository must publish a real pull-request check called
`ci-required` that covers **all of its mandatory CI**. A final job with
`if: always()` and `needs` can aggregate jobs within one workflow,
including invoked reusable workflows. A `needs` dependency cannot observe
independent workflow runs. If mandatory checks remain in different workflows,
introduce and validate a reliable coordinator rather than a green placeholder.

The aggregate must fail when a required test fails, is cancelled or is
unexpectedly missing. Define allowed skips explicitly; a skipped mandatory
test must not silently count as success. Test success, failure, cancellation,
skips, reruns and the head or merge commit carrying the reported result.
Adding a new mandatory job requires updating the coordinator contract.

The policy uses `strict_required_status_checks_policy: true`, requiring an
up-to-date branch when enforcement is activated.

## Bypass and auto-merge

The proposed CI gate allows organization administrators to bypass the
*CI ruleset* in `pull_request` mode. Document the reason for an exceptional
manual merge in the PR. The bypass of this ruleset does not remove other
applicable rulesets, such as required reviews or separately configured DCO
checks. GitHub auto-merge waits for required checks only, not every workflow.

## Deployment and verification

1. Implement and test `ci-required` in each consumer repository.
2. Submit a reviewed change to set `required-ci-gate.enforcement` to
   `active` only after the consumer contract has been verified.
3. Run [GitHub governance](../.github/workflows/github-governance.yml)
   with `apply=false`, and inspect each repository's planned changes.
4. Run with `apply=true` only after an explicit review of that plan.
   Verify the remote rulesets and run a final dry-run for drift.

Merging changes to the JSON does not apply them. The `ruleset-sync`
environment protects the GitHub App credential with administration-write
permission and currently requires approval for scheduled plans as well as
manual apply. Unattended drift monitoring needs a separate security review;
do not remove that protection solely to avoid approvals.

The [dependency auto-merge policy](dependency-update-policy.md) covers a
different workflow and must not be confused with ruleset bypass.
