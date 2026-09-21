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
- Reusable workflow/action implementation lives in `LibreCodeCoop/github-workflows`.
- `workflow-templates/**` is the organization catalog consumed by repositories; do not add product-specific business logic here.
- Repository-local licenses, README files and `AGENTS.md` stay in their own repositories.

## Quality gates

Changes to workflows/configuration should pass DCO, actionlint and zizmor. Governance changes should be planned before apply.

## Security

- Never commit GitHub App private keys or tokens.
- Keep action pins immutable.
- Treat governance apply as a privileged operation.
- Preserve reviewable PR-based changes for repository policy.

## SPDX / REUSE

New LibreCode-owned files use AGPL-3.0-or-later and must include appropriate SPDX metadata.
