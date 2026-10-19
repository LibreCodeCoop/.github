<!--
SPDX-FileCopyrightText: 2026 LibreCode coop and contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Release workflow implementation boundaries

GitHub Actions workflows orchestrate reusable, versioned Release Tool Actions.
They must not independently implement XML/JSON parsing, permission policies,
or stable-branch selection with inline Python or shell programs.

The organization publication Action delegates permission validation to the
release-tool authorization-check adapter and checkout metadata to build-inspect.
When package.json is missing, build-inspect returns no Node/npm versions and
Node build steps must not run. A present package.json without engines uses
Node ^24 and npm ^11.3.

The nightly workflow runs daily or on manual dispatch. It selects the highest
stable<N> branch using stable-select and checks out that exact ref. The tag and
release notes always refer to the checked-out commit, never the main branch
commit that triggered the scheduled run. When no stable branch is available,
the publishing job is skipped.

The release finalization workflow uses pull_request_target only for closed,
merged release preparation PRs with verified branch and marker metadata.
Do not filter these events using changed file paths.

Validation boundaries:

1. Release Tool PHPUnit tests validate parsed build metadata, default values,
   malformed or missing files, injection attempts and GitHub outputs.
2. Release Tool public Action acceptance tests pin adapter contracts.
3. Organization workflow tests validate orchestration, immutable pins,
   branch selection and sensitive event guards; actionlint and zizmor
   validate workflow structure and security.
4. Live App Store publishing and nightly tag mutations require a separate
   controlled integration run, not an ad hoc CI dry run.

Both repositories pin shared Actions to a single immutable release-tool commit.
Verify that the corresponding versioned PHAR is published and its checksum
valid before consuming the release.
