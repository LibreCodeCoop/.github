<!--
SPDX-FileCopyrightText: 2026 LibreCode coop and contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Cross-repository automation

LibreCode distributes managed workflow templates through `LibreCodeCoop/.github`. Consumer repositories opt in by installing `sync-workflow-templates.yml`; there is no central consumer registry.

## Flow

```text
github-workflows
    -> LibreCodeCoop/.github catalog
    -> consumer sync-workflow-templates.yml
    -> actions/sync-workflows
    -> reviewable consumer pull request
```

The updater manages workflows already installed in the consumer repository. It records catalog state in `.github/actions-lock.txt`, reapplies an optional `<workflow>.patch`, and refuses to overwrite unexplained local divergence.

## Authentication

The installed updater selects authentication with the repository variable `WORKFLOW_SYNC_AUTH_MODE`:

- `librecode-app` — LibreCode-managed repositories; uses `LIBRECODE_WORKFLOW_APP_ID` and `LIBRECODE_WORKFLOW_APP_PRIVATE_KEY`.
- `github-app` — independent consumers; uses `WORKFLOW_SYNC_APP_ID` and `WORKFLOW_SYNC_APP_PRIVATE_KEY`.
- `token` — uses `WORKFLOW_SYNC_TOKEN`.
- `github-token` — uses the workflow `GITHUB_TOKEN`.

For independent projects, prefer a consumer-owned GitHub App. The updater needs repository permissions **Contents: write**, **Pull requests: write**, and **Workflows: write** because it updates files under `.github/workflows`.

The `github-token` mode is explicit because events created with `GITHUB_TOKEN` may not trigger the repository's normal pull-request automation.

## Install and update workflows

1. Install the desired templates from the organization catalog.
2. Install `sync-workflow-templates.yml`.
3. Configure one authentication mode.
4. Run **Update workflows** manually once.
5. Review and merge the generated update PR.
6. Confirm a subsequent run is a no-op.

After installation, the updater runs weekly and can also be dispatched manually. It updates the installed workflows, including itself, through normal reviewable pull requests.

Consumer-specific changes belong in `.github/workflows/<workflow>.patch`. Do not edit a managed workflow directly when the difference should survive synchronization.

## Publishing templates

`.github` is the source of truth. `LibreCodeCoop/.github` is the distribution catalog, not an editing source.

Only templates listed in `workflow-catalog.json` are published. Generated or experimental workflows should not be added to the catalog until they are ready for consumers.

## LibreCode catalog credentials

Catalog publication uses the **LibreCode Workflow Automation** GitHub App. Its credentials are stored in `LibreCodeCoop/.github`:

- variable `LIBRECODE_WORKFLOW_APP_ID`;
- secret `LIBRECODE_WORKFLOW_APP_PRIVATE_KEY`.

Write-capable jobs mint short-lived installation tokens scoped to the destination repository. The private key must never be committed.

For LibreCode-managed workflow synchronization the same App must be installed on the consumer repository and its credentials must be available to that repository's Actions context.

## Key rotation

1. Generate a new private key in the GitHub App settings.
2. Replace the Actions secret.
3. Validate catalog publication and one consumer synchronization.
4. Delete the old key.

Do not delete the old key before validating the replacement.
