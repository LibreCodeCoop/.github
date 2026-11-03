<!-- SPDX-FileCopyrightText: 2026 LibreCode Coop and contributors -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Engineering standards decision matrix

Snapshot: 2026-11-03, inspected on default branches. The source of truth for organization policies is `LibreCodeCoop/.github`, not this summary. **Policy intent, implementation, and active enforcement are different states.**

Definitions: **Required** = explicit applicable governance rule or release/PR contract in this skill; **Recommended** = repeated, well-supported engineering practice but not universal enforcement; **Conditional** = applicability depends on code, runtime, threat model or distribution; **Product-specific** = do not transfer automatically. The following classification is a **proposed engineering baseline**, not an enacted organization-wide ruleset.

| Control | Classification | Adoption / enforcement evidence | Verification or acceptance criterion |
| --- | --- | --- | --- |
| Reviewed PR, one approval, resolved threads, non-fast-forward protection on default/stable* | Required where `protected-branches` is applied | `governance.config.json` declares default active policy; application on a concrete repository must be queried | Inspect effective ruleset and PR approvals; no direct merge via this skill |
| CODEOWNERS with appropriate actual reviewer | Conditional operational prerequisite for effective owner review | `.github/CODEOWNERS` exists in org-config; only a narrow file rule confirmed in `profile_fields`; absent at observed `suitecrm-mcp`, `akaunting-mcp` paths | Check consumer's effective CODEOWNERS mapping; do not infer inheritance |
| Conventional Commits and DCO signoff | Required for commits created through this skill; recommended/adopted by several projects | `suitecrm-mcp`, `akaunting-mcp` PR checks; `nfse-php` commit workflow; organization-config CI declares DCO | Inspect every new commit trailer and PR checks, not only PR title |
| Cryptographically signed commits | Required for this skill's authorized writes; not proven to be enforced org-wide | `suitecrm-mcp/CONTRIBUTING.md` recommends; `akaunting-mcp/AGENTS.md` instructs signing | Git Signing MCP reports verified, DCO matches author; record SHA |
| GitHub Actions remote `uses:` pinned to full SHA and version comment | Required for newly created/changed workflows under LibreCode convention | `.github/docs/repository-governance.md`; executable `scripts/check_workflow_policy.py`; not all consumers yet migrated | Run authoritative checker, actionlint, zizmor; verify upstream version/commit |
| Least-privilege workflow `permissions` and checkout no persisted creds | Required for new workflows | `.github/scripts/check_workflow_policy.py` plus observed CI | Inspect effective job privileges; reject `write-all`; test untrusted PR paths |
| `ci-required` aggregate | Conditional: only if consumer explicitly uses it | Declared policy is **disabled** for named consumers until proven | Cover all mandatory jobs, failure/cancellation/missing/skip scenarios and commit matching; no dummy job |
| Language-native lint, static analysis, tests and formatting | Recommended baseline, tools conditional | PHPStan/PHPUnit/CS Fixer in two MCPs; Psalm, Behat/Playwright in NFSe/Nextcloud apps; Bats in Docker repo | Run exact local and CI commands; negative and integration tests where relevant |
| Dependency locking, reproducible install and audit | Conditional to language/dependencies, strongly recommended | Composer locks in MCPs, npm lock in profile_fields, Composer audit workflows | Reproduce locked installation and run native audit when applicable |
| Immutable container inputs, runtime smoke, secrets separation | Conditional to container/distribution | `suitecrm-mcp` Docker smoke; `nextcloud-docker` Bats and pinned digest management | Build + actual smoke, persistence verification, least privilege, image scan |
| REUSE/SPDX identifiers and complete license text | Required for repos using REUSE policy; proposed default for new repos | REUSE action catalog template, REUSE.toml/LICENSES in PHP repos | `reuse lint` with matching license files; manual licensing review |
| AGPL-3.0-or-later as default license for new LibreCode-owned projects | Institutional default (stated by maintainer; not proven enforced via GitHub ruleset), **not** a universal ban on exceptions | Organization maintainer explicitly confirmed AGPL default on 2026-11-03; sampled LibreCode projects and `.github` use AGPL. No declarative licensing rule was observed | On create: use AGPL by default with complete canonical text; if explicitly changed, record licensing decision and compatibility review. On audit: never silently relicense existing work |
| README and contribution/security reporting | Recommended, conditional depth | Repeated MCP/NFSe root docs; repo-specific SECURITY policies | Document actual setup, disclosure route, operational boundaries; test examples |
| Secrets and public release scope scanning | Conditional to public/distributed/sensitive repos; recommended | `akaunting-mcp` secret & source scope workflows | Scan tree and history where appropriate; synthetic fixtures, no production data |
| Release/tag/stable branch workflow | Conditional to distribution and support matrix | `.github/docs/release-workflow-architecture.md`, Nextcloud app templates | Package validated exact checked-out ref; explicit publish authorization |
| Fiscal/multi-tenant/Nextcloud product tests | Product-specific | `akaunting-nfse` API/MySQL/Behat/Playwright; LibreSign backports | Transfer contract-thinking, not their services, runtime or exact workflows |

## Non-negotiable interpretation rules

1. A documented desired rule does not prove effective remote branch protection. The active `required-ci-gate` option is disabled; do not activate on recommendation alone.
2. Catalog templates are a maintained source, not universal compatibility guarantees. A Nextcloud-specific Psalm template is not a generic PHP workflow. Do not fabricate a Python/Go/TypeScript template as already institutional.
3. Signed commits and Conventional Commits/DCO are distinct. A signed commit can fail DCO; a DCO trailer does not prove a cryptographic signature.
4. Testing one code path is not evidence of coverage adequacy, security or production readiness. Require meaningful assertions, negative cases and actual execution.
5. Contexts like `ci-required`, `DCO`, `actionlint` and `zizmor` must come from real checks covering the expected ref, not statuses manufactured for protection.
6. A local audit returns best-effort findings. Prove GitHub-side rulesets/checks with remote inspection before asserting conformance.

Consult [evidence-ledger.md](evidence-ledger.md) for direct source URLs, observed vs. missing adoption, and known exceptions.
