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

- `required-ci-gate-active` shares the **same `Require CI` ruleset contract**
  as the staged `required-ci-gate`, with only enforcement enabled. It is
  selected for `LibreCodeCoop/agent-skills`, whose `ci-required` producer
  passed on its merged PR #1. The default `protected-branches` ruleset is
  inherited automatically; no project-specific copy is required. Other staged
  repositories keep their disabled CI rule until individually verified. This
  JSON change does **not** apply CI rules remotely: a separate reviewed plan
  and authorized Apply is still required.

The configuration expresses desired policy, not proof that a ruleset was
already applied on GitHub. An organization-wide rollout is not automatic:
the consumer must have the matching check before protection is enabled.
Other repositories and stable branches are outside this initial CI gate.

## GitHub Actions: immutable references and annotated versions

All remote `uses:` references must use a full **40-character Git commit SHA**,
not mutable `@vN`, `@main`, or a shortened hash. For actions with tagged
releases, keep the **upstream** version next to the SHA (for example
`# v4.4.0` or `# 4.0.0`) so updates can be reviewed and detected by
Dependabot. Do not invent a version number. Local `./` actions are exempt;
in-house actions without version tags use an explicit source description,
such as `# main at abcdef1`.

The [workflow-policy checker](../scripts/check_workflow_policy.py) tests
this convention for organization-owned workflow templates and workflows.
Other repositories must adopt equivalent CI checks (or a centrally required
workflow) and configure the `github-actions` ecosystem in Dependabot.
These local checks are **not** an organization-wide requirement by themselves.

GitHub also provides an organization-wide Actions setting named
**Require actions to be pinned to a full-length commit SHA**. It blocks
execution of unpinned actions but does **not** verify the adjacent version
comment. At the time of the audit on 2026-10-23, LibreCodeCoop's
`sha_pinning_required` setting was **false**. Enabling it without migration
would break existing workflows referencing tags.

Adopt the organization-wide gate only after this staged rollout:

1. Inventory unpinned `uses:` declarations in active repositories
   (including private ones), excluding relative actions; track the backlog.
2. Fix each affected workflow and its Dependabot configuration through
   reviewed pull requests, validating the exact upstream tag -> commit SHA.
3. Verify tests and production/release workflows, including workflows that
   only execute on push, tag, or dispatch.
4. Enable `sha_pinning_required=true` under organization **Settings >
   Actions > General** once those repositories are compliant; recheck
   execution and maintain a rollback procedure.
5. Keep version comments covered by CI / organization-required workflows.
   The GitHub-native policy alone cannot enforce that annotation.

Relevant GitHub guidance:
[organization Actions policy](https://docs.github.com/en/organizations/managing-organization-settings/disabling-or-limiting-github-actions-for-your-organization),
[secure use of Actions](https://docs.github.com/en/actions/reference/security/secure-use).

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

## Common ruleset verification and repository onboarding

The `protected-branches` policy is the default for eligible public,
non-archived repositories, including newly created repositories. It governs
reviews, Code Owner approval, resolved conversations, deletion and force-push
restrictions, and PR-only bypass for authorized administrators and maintainers.
Repository-specific CI status checks are not part of this shared policy.

Scheduled and configuration-change workflows run a **read-only** organization
plan. If any eligible repository is missing a required common ruleset or its
configuration drifts, the plan fails so that the deviation is visible in
GitHub Actions. Manual plans permit drift for review before an authorized
apply. A failed plan never changes GitHub settings, and passing the plan is
not evidence that any pending change has been applied.

New repositories are not protected at the instant they are created: GitHub
Actions in this `.github` repository do not receive the `repository.created`
webhook of every repository in the organization. A **daily read-only scan**
reports missing common rulesets as failed governance checks; it never writes.
After reviewing the plan, use **Actions > GitHub governance > Run workflow**
with `repository` set to the target repository, `apply=true` and the default
`onboard_only=true`, and approve the `ruleset-sync` environment. The new mode:

- creates **only** the missing organization-default ruleset;
- refuses repositories with classic branch protection or no initialized
  default branch;
- leaves all existing rulesets, product CI/DCO requirements, metadata and
  branch-protection settings untouched;
- flags an existing divergent ruleset or conflicting direct-push bypass for
  manual review, rather than changing it.

The normal full-reconciliation mode remains possible only by setting
`onboard_only=false` during an explicitly approved manual run. It must not be
used merely to get an onboarding job green. The Apply GitHub App token needs
repository Administration (write) only and should be scoped to the named
repository. The separate caller `GITHUB_TOKEN` supplies read-only public
repository content classification; it is never used for administration or
mutations. The GitHub App must be installed on that repository. Private and
archived repositories are outside the configured public discovery scope.

**Nextcloud translation bot safeguard.** For repositories with
`appinfo/info.xml`, the caller's `protected-branches` policy has a conditional
`User`/`always` bypass for `nextcloud-bot` (GitHub user ID `20296731`). This
allows direct translation pushes to `main`; the general policy does not grant
this exception to non-Nextcloud repositories. Any additional active DCO or CI
ruleset that covers these apps must independently preserve the bot bypass.
Historical regressions are documented in LibreCodeCoop/profile_fields#148,
LibreCodeCoop/extract#148 and LibreSign/libresign#8399/#9172. Never activate a
new mandatory-check ruleset without verifying that it permits this account.

New repositories with no default-branch commit are intentionally skipped until
their contents can be classified. If a regular repository later becomes a
Nextcloud app, reconcile its conditional bypass **before** enabling automated
translations; a scheduled read-only scan can identify drift but cannot safely
assume the repository's future purpose.

The engine reconciles **rulesets**, not legacy branch protection. Both may
apply simultaneously, and the separate legacy protection can block a PR even
when the common ruleset allows a bypass. Check both policy surfaces:

```sh
gh api repos/OWNER/REPO/rules/branches/BRANCH
gh api repos/OWNER/REPO/branches/BRANCH/protection
```

A 404 for the second command indicates no classic branch protection. Before
removing one, compare its mandatory checks, signatures, reviews and other
restrictions with the effective rulesets. A repository-scoped migration must
preserve any stricter requirements and be reviewed independently; the common
plan does not delete classic branch protection or configure product-specific
CI checks.

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
permission and requires approval for privileged manual apply. Scheduled
read-only plans do **not** require environment approval and never modify
repository policies. Do not remove the approval gate to enable unattended
provisioning without a separate security design and review.

The [dependency auto-merge policy](dependency-update-policy.md) covers a
different workflow and must not be confused with ruleset bypass.

## Automatic baseline onboarding for new public repositories

The [automatic onboarding workflow](../.github/workflows/github-governance-auto-onboard.yml)
checks for new eligible **public** repositories twice an hour. Its discovery
uses a read-only token, validates repository names and existence of the default
branch, and selects only repositories that currently have **no rulesets**.
Existing custom rulesets are treated as manual exceptions and are never
rewritten or deleted. Once a ruleset already exists, automatic provisioning
leaves it untouched, even if it differs from the institutional default.

For each candidate, a short-lived GitHub App token is scoped to **one repo**.
The pinned shared engine runs `onboard-only=true`, checking live rulesets and
classic branch protection again immediately before creating the missing
institutional `protected-branches` rule. Any ambiguity, API error, missing
permission or manual protection fails closed for review. This workflow **does
not** change existing rules, enable CI checks, update metadata, remove bypasses
or perform full reconciliation.

**One-time configuration before activation:**

1. Configure a dedicated `ruleset-auto-onboard` Actions environment with a
   deployment restriction to protected `main`. It has no human approval
   requirement, unlike `ruleset-sync`, because onboarding is scheduled.
2. Set `AUTO_RULESET_APP_CLIENT_ID` as an environment variable and
   `AUTO_RULESET_APP_PRIVATE_KEY` as an environment secret. The dedicated
   GitHub App installation must have Administration (write) only on the managed public repositories. A
   separate short-lived, read-only `github.token` supplies public content
   classification, without granting the App Contents (read); each App token
   is restricted by the
   job to the selected repository. Do not relocate or expose the privileged
   `ruleset-sync` credentials.
3. After an independent review of this credential boundary and `main`
   protection, set the **repository variable**
   `AUTO_RULESET_ONBOARDING_ENABLED=true`. Until then, the new workflow is
   intentionally disabled.
4. Run the workflow manually once, inspect the resulting scope and GitHub
   rulesets, then let the schedule handle subsequent new public repositories.

GitHub scheduled workflows are best effort. **This is eventual onboarding, not
an instantaneous guarantee at repository creation time.** Empty repositories
are skipped until their default branch is initialized. Private repositories
remain outside the GitHub Free-supported ruleset scope. A local exception may
add restrictions, but cannot silently weaken an existing institutional
ruleset. Policy changes and exceptional reconciliation of existing rules
continue to require a reviewed `ruleset-sync` Apply.
