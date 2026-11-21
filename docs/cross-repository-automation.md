<!--
SPDX-FileCopyrightText: 2026 LibreCode coop and contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Cross-repository automation

LibreCode distributes managed workflow templates through `LibreCodeCoop/.github`. Consumer repositories opt in by installing `sync-workflow-templates.yml`; there is no central consumer registry.

## Flow

```text
LibreCodeCoop/.github catalog
    -> consumer sync-workflow-templates.yml
    -> actions/sync-workflows
    -> reviewable consumer pull request
```

For gradual adoption, consumers can pass `include: npm-audit-fix.yml` to the
`sync-workflows` action to enroll just that template while leaving other local
workflows and existing lock entries untouched. An empty `include` retains the
standard behavior of reconciling all installed catalog workflows. The selection
must reference existing catalog filenames; missing filenames cause an error.

The updater manages workflows already installed in the consumer repository. It records catalog state in `.github/actions-lock.txt`, reapplies an optional `<workflow>.patch`, and refuses to overwrite unexplained local divergence.

## Authentication

The workflow uses organization-neutral settings; each consumer can select its
own credentials. Configure `WORKFLOW_SYNC_AUTH_MODE` as:

- `github-app` (default) — `WORKFLOW_SYNC_APP_CLIENT_ID` (repository variable)
  and `WORKFLOW_SYNC_APP_PRIVATE_KEY` (Actions secret).
- `token` — `WORKFLOW_SYNC_TOKEN` (Actions secret).
- `github-token` — the built-in `GITHUB_TOKEN`.

The `github-app` mode requires the complete variable/secret pair; it fails
before any write when either value is missing. Use a consumer-owned GitHub App
with **Contents: write**, **Pull requests: write**, and **Workflows: write**
permissions to update files under `.github/workflows`.

The `github-token` mode is explicit because events emitted using
`GITHUB_TOKEN` may not trigger normal pull-request automation.

## Install and update workflows

1. Install the desired templates from the organization catalog.
2. Install `sync-workflow-templates.yml`.
3. Configure one authentication mode.
4. Run **Update workflows** manually once.
5. Review and merge the generated update PR.
6. Confirm a subsequent run is a no-op.

After installation, the updater runs weekly and can also be dispatched manually. It updates the installed workflows, including itself, through normal reviewable pull requests.

Consumer-specific changes belong in `.github/workflows/<workflow>.patch`. Do not edit a managed workflow directly when the difference should survive synchronization.

The catalog updater targets only the consumer's default branch by default. Projects with maintained long-lived release branches should declare those branches through a consumer-local patch to `sync-workflow-templates.yml`; branch lifecycle is consumer policy and must not be hard-coded in the organization template.

## Submodule dependency commands

`command-submodule-pr.yml` tracks a pinned upstream workflow from
`nextcloud/3rdparty`; its generic changes live in `patches/nextcloud/`
and are verified against immutable upstream checksums.

`command-update-submodule.yml` is LibreCode-owned. It delegates to the
version-pinned, tested `actions/update-submodule` Action: the Nextcloud Server
command is a conceptual reference, but its implementation is intentionally
not copied because it updates a moving branch tip and can rewrite commits.

A consumer must install each workflow and configure its parameters using
Actions variables or a consumer-local `.github/workflows/<name>.yml.patch`:

- `command-submodule-pr.yml`: `SUBMODULE_PR_COMMAND`,
  `SUBMODULE_TARGET_REPOSITORY` and `SUBMODULE_PATH`. The optional
  `SUBMODULE_PR_LABELS` is a comma-separated list of labels already present in
  the target repository; `SUBMODULE_PR_REVIEWER` is an optional GitHub login,
  or `commenter` to request review from the maintainer who invoked the command.
- `command-update-submodule.yml`: `SUBMODULE_UPDATE_COMMAND`,
  `SUBMODULE_SOURCE_REPOSITORY` and `SUBMODULE_PATH`.

The creation command publishes its submodule gitlink using a GitHub App bot-signed
commit with DCO, and rejects an unverified destination commit. The same bot
identity is used for the commit author and sign-off. It expects a Composer lockfile
in the source PR. It checks
all source PR checks with read-only `checks` and `statuses` permissions and
refuses failed, pending, absent or stale checks. It revalidates the source HEAD
before pushing to the target. A failed target PR creation can leave a branch
without a PR; do not force-push or overwrite that branch to retry.

The update
command requires a linked source PR already merged into the same target branch
and uses its exact merged SHA. Both commands require maintainer authorization,
repository-hosted PR branches and a scoped publishing credential. No force
push is performed. Publishing credentials are not available to dependency
analysis or staging steps.

## Publishing templates

`LibreCodeCoop/.github` is the source of truth for LibreCode-managed workflow templates and the distribution catalog consumed by repository updaters. Templates derived from external upstream sources are refreshed through the pinned upstream/patch pipeline rather than edited as independent downstream implementations.

YAML workflows present in `workflow-templates/` form the distribution catalog.
Generated or experimental workflows should not be added until they are ready for consumers.
For the npm audit workflow, consumers need a matching local patch and configured
GitHub App credentials before enrollment.

## Catalog credentials

Catalog publication uses the **LibreCode Workflow Automation** GitHub App. Its credentials are stored in `LibreCodeCoop/.github`:

- variable `WORKFLOW_SYNC_APP_CLIENT_ID` (GitHub App Client ID);
- secret `WORKFLOW_SYNC_APP_PRIVATE_KEY`.

Write-capable jobs mint short-lived installation tokens scoped to the destination repository. The private key must never be committed.

For LibreCode-managed workflow synchronization the same App must be installed on the consumer repository and its credentials must be available to that repository's Actions context.

## Key rotation

1. Generate a new private key in the GitHub App settings.
2. Replace the Actions secret.
3. Validate catalog publication and one consumer synchronization.
4. Delete the old key.

Do not delete the old key before validating the replacement.
