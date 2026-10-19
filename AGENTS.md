<!--
SPDX-FileCopyrightText: 2026 LibreCode coop and contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Agent guidance

## Purpose

This repository is the LibreCode Coop organization configuration repository. It owns the public organization profile, community defaults, workflow catalog and the caller configuration for repository governance.

## Boundaries

- `governance.config.json` is the declarative source for LibreCodeCoop repository governance and supported GitHub metadata.
- The governance engine itself lives in `LibreCodeCoop/github-governance`.
- Organization workflow templates and helper Actions live in this repository. Product-specific release behavior belongs in its owning product repository, such as `LibreCodeCoop/release-tool`.
- Release workflows must consume testable, versioned release-tool Actions for authorization and build metadata; do not introduce duplicate inline Python or shell parsers in workflow YAML.
- `workflow-templates/**` is the organization catalog consumed by repositories; do not add product-specific business logic here.
- Repository-local licenses, README files and `AGENTS.md` stay in their own repositories.

## Quality gates

Changes to workflows/configuration should pass DCO, actionlint and zizmor. Governance changes should be planned before apply.

## Upstream refresh and diff hygiene

- Treat `upstream/vendor/**`, `patches/nextcloud/**`, and
  `workflow-templates/**` as different review surfaces.
- Never rewrite an entire downstream patch to fix an isolated upstream change.
  Preserve the smallest applicable hunks and avoid whitespace-only churn.
- Always review `git diff --ignore-all-space` alongside the normal diff.
- Validate source checksums, full template rendering, and Python tests before
  publishing an upstream refresh PR; verify a second render is unchanged.
- The App Store publication template is LibreCode-owned. Its upstream copy is
  reference material, not a source for regenerating the consumer wrapper.
- Use signed, DCO-compliant, incremental commits and preserve PR review history.

## Security

- Never commit GitHub App private keys or tokens.
- Keep action pins immutable.
- Treat governance apply as a privileged operation.
- Preserve reviewable PR-based changes for repository policy.

## SPDX / REUSE

New LibreCode-owned files use AGPL-3.0-or-later and must include appropriate SPDX metadata.
