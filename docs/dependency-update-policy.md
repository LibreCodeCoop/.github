<!--
SPDX-FileCopyrightText: 2026 LibreCode coop and contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Dependency update and auto-merge policy

Dependency automation is more privileged than lint or test workflows because it can
create, approve or merge pull requests. It is therefore not automatically copied from
Nextcloud into the LibreCode catalog.

## Allowed actors

Automatic approval or merge may only act on pull requests created by explicitly
recognized dependency bots:

- GitHub Dependabot;
- other bots only after an explicit organization-level decision and equivalent actor
  verification.

Do not auto-approve arbitrary pull requests based only on branch naming or labels.

## Merge policy

Default policy:

- patch and minor dependency updates may be eligible for auto-merge after all required
  checks pass;
- major updates require human review unless a repository documents a narrower exception;
- security remediation may create a pull request automatically but must not bypass
  required checks;
- approval and merge are separate operations and should remain independently auditable.

## Credentials

Prefer the `LibreCode Workflow Automation` GitHub App for cross-repository or
workflow-file mutations.

Do not require a maintainer's personal access token in a shared template. A PAT-based
workflow stays repository-local until it can be replaced with an organization-owned
credential model.

## pull_request_target

A workflow using `pull_request_target` must:

- verify the pull request actor before any privileged action;
- avoid checking out or executing untrusted pull-request code with write credentials;
- grant only the permissions required for metadata, approval or merge operations;
- pin every external Action to a full commit SHA.

## Distribution decision

Dependency/update workflows are cataloged only when their credential and actor model is
generic across LibreCode consumers.

Repository-specific combinations of Dependabot, Renovate, labels, branch naming or PATs
remain local workflows. The organization catalog should not centralize them merely to
reduce YAML duplication.

## Current decisions

- `dependabot-approve-merge.yml`: do not migrate the existing Extract workflow until it
  uses the organization policy above and an organization-owned credential model.
- `npm-audit-fix.yml`: keep repository-local; it may create a remediation PR but should
  not imply automatic approval/merge.
- obsolete Nextcloud OCP auto-merge workflows are not migrated.
