---
name: librecode-project-bootstrap
description: Bootstrap or audit LibreCode Coop software repositories across PHP, Python, TypeScript, JavaScript, Go and other languages. Use for new repository creation, migration of existing project quality controls, GitHub governance alignment, CI/CD and supply-chain hardening, reusable test setup, or compliance gap assessments. Cross-check the live LibreCodeCoop/.github policies and workflows, adapt to the project's language and deployment model, execute checks, produce evidence, and prepare signed DCO pull requests only when authorized.
---

<!-- SPDX-FileCopyrightText: 2026 LibreCode Coop and contributors -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# LibreCode project bootstrap

Operate in **create** or **audit** mode. The skill is an engineering workflow, not a promise that generated files alone constitute compliance.

## Intake and scope

Record project name, purpose, owner/reviewers, programming language, supported runtime versions, application type (library, CLI, service, plugin, container or other), distribution channel, intended environment, license/SPDX identifier, and repository visibility. Identify data sensitivity, authentication, multi-tenant and migration boundaries. Request missing decisions that block safe execution; **never infer the license, production credentials, or a release policy**. Prefer a minimally viable project and avoid adding optional infrastructure.

Read [institutional-standards.md](references/institutional-standards.md) to distinguish institutionally defined policy, repeated conventions, and product-specific requirements. Refresh against the live `LibreCodeCoop/.github` repository when connected: its configuration is authoritative over this dated evidence snapshot. Read [evidence-ledger.md](references/evidence-ledger.md) before claiming organization-wide adoption.

## Create a project

1. Inspect target directory and Git state. Refuse destructive overwrites; use a new working branch. Confirm user authorization before repository mutation.
2. Choose the smallest language toolchain from [language-profiles.md](references/language-profiles.md). For a simple CLI prototype, `python3 scripts/bootstrap.py --help` creates a dependency-free baseline; **it does not finish the engineering review**. For other application types, implement native project structure directly. Do not invent business endpoints, databases, Docker, or deployment assets.
3. Select and install lint, formatter, static analysis, unit/integration/negative tests, dependency audit and lock strategy appropriate to the runtime; use native tool configuration and package-manager scripts rather than long embedded workflow shell scripts. Run commands and repair real failures. Record unexecutable checks as pending, not passing.
4. Use [github-governance.md](references/github-governance.md) and [security-and-supply-chain.md](references/security-and-supply-chain.md). Adopt existing organizational workflows from `LibreCodeCoop/.github/workflow-templates/` where suitable, respecting catalog provenance, `.github/actions-lock.txt` and consumer `.patch` files. Adapt unsupported languages explicitly and do not submit unreviewed templates to the catalog. Use immutable SHA references, review upstream versions, and run policy checker, actionlint and zizmor when available.
5. Apply [documentation.md](references/documentation.md): produce only relevant README, contribution/security, licensing, architecture/development/operations documentation. Include synthetic examples, SPDX attribution and actual license text. A license identifier alone is not REUSE compliance.
6. Produce evidence: commands and exit codes, negative-test failures that are correctly rejected, build/package artifacts, dependency audit, workflow results, coverage interpretation, risks and residual gaps. Do not claim a green CI check before GitHub reports it.
7. Only when authorized, follow [contribution-and-review.md](references/contribution-and-review.md): conventional commit, DCO signoff, authenticated cryptographic signing, reviewed branch/PR. Do not merge, deploy, modify organization rulesets, publish releases, or expose credentials without separate authorization.

## Audit an existing project

1. Capture branch/HEAD, inventory manifests/workflows/docs/CI/rulesets and identify the actual runtime. Inspect recent relevant pull requests, not only checked-in files.
2. Run `python3 scripts/audit_project.py <project>` for read-only local heuristics; consider its UNKNOWN results explicitly. Verify actual GitHub checks, rulesets, CODEOWNERS effectiveness, coverage, security behavior and current template sync separately. Never mistake a present file for an operating control.
3. Compare against [institutional-standards.md](references/institutional-standards.md) with `required`, `recommended`, `conditional`, `product-specific` labels and evidence links. Separate *policy intent*, *observed implementation*, *enforcement*, and *audit judgment*.
4. Return a prioritized diff/plan. Do not overwrite local changes or reconfigure protection. If remediation is authorized, implement focused patches, run checks, and prepare a signed PR.

## CI integrity and acceptance

A `ci-required` job is legitimate only when it observes **all required jobs for the same effective revision**, including failures, cancellations, missing jobs and unapproved skips. `needs` cannot observe independent workflow runs. An unverified aggregator is an **unresolved governance gap**, never a fabricated green gate. See [github-governance.md](references/github-governance.md); `scripts/check_ci_results.py` only validates an explicit result manifest and is **not** a GitHub CI coordinator by itself.

## Deliverable contract

Report: repository and pinned HEAD; requested scope; selected controls and sources; executed commands and results; matrix of pass/fail/unknown/not-applicable with reasons; unverified or missing dependencies; signed commit and PR status (if applicable); follow-up approvals. Provide a rollback path for proposed changes. Never transform recommended or product-specific practices into universal institutional mandates without supporting governance evidence.
