<!-- SPDX-FileCopyrightText: 2026 LibreCode Coop and contributors -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Security and supply chain controls

## Baseline threat modeling

Identify trust boundaries first: public pull requests, CI tokens, dependencies, runtime secrets, tenant boundaries, authentication, data retention, network entrypoints, release artifacts. Do not add Docker, a secret manager, a database, privileged GitHub token or public tunnel merely to match another project's architecture.

| Control | How to verify | Notes |
| --- | --- | --- |
| Third-party Actions immutable refs | Run authoritative `LibreCodeCoop/.github/scripts/check_workflow_policy.py` and actionlint; compare SHA with published upstream release | `@vN` and shortened hashes are not acceptable for new LibreCode workflows; annotate true upstream version |
| Workflow privilege and untrusted PRs | Inspect `permissions`, checkout credential persistence, event and actor gates; run zizmor | `pull_request_target` is especially sensitive; no PR checkout/execution with write credentials |
| Secret exposure | Gitleaks or equivalent on files and Git history, review examples and logs | Scans cannot prove secret-free history; never paste secrets in reports |
| Dependencies | Native audit: `composer audit`, `npm audit`, `pip-audit`/`uv audit` where available, `govulncheck`; verify install from locked inputs | Tool availability and advisory freshness must be reported; do not replace locked install with untracked updates |
| Negative security tests | Attempt unauthorized access, cross-tenant access, invalid tokens, malicious URLs and corrupted data where applicable | No production accounts/data, no real fiscal transmissions |
| Container safety | `docker build`, `docker compose config --quiet`, test startup/readiness, permissions, volume persistence, vulnerability scan | Do not publish images as a smoke-test shortcut; explicit digest/architectures when useful |
| Public release scope | Whitelist expected source/config, scan distribution archive; reject `.env`, keys, internal hosts and local debug artifacts | `akaunting-mcp` includes a self-tested public-scope checker; not every project needs that implementation |
| Release integrity | Verify exact ref, protected branch, reproducible package/checksum, approval, published artifact comparison | Publishing is never implied by CI success |

## Credential and deployment boundaries

Use `.env.example` with placeholders only when configuration exists; never commit actual `.env`, credentials, customer exports, private incident reports, SSH keys or operational backup files. Keep production-only runbooks in an authorized private location if they contain sensitive infrastructure details. Separate source build from deployment credentials and mutable production operations. Ensure test environments use disposable synthetic records.

## Dependency automation

Prefer one updater per dependency ecosystem, avoiding overlapping Dependabot and Renovate ownership. For example, `suitecrm-mcp` uses Dependabot for Composer and GitHub Actions while Renovate manages Dockerfile/Compose; `akaunting-mcp` instead uses Dependabot for Docker as well. There is no universal single-bot rule. Major updates require human review by default; approved patch/minor automation must still pass required checks. Do not enable auto-merge on this skill's PRs.

## Checklists are not checks

Every item must map to a command, CI check, invariant test or explicit human signoff. `audit_project.py` may flag a missing config but cannot prove remote branch protection, secret-free history, or quality of business assertions. `check_ci_results.py` is only a unit-testable result evaluator and cannot publish `ci-required`.
