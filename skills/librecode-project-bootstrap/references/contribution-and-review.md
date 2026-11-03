<!-- SPDX-FileCopyrightText: 2026 LibreCode Coop and contributors -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Contribution, signing and review

## Commit contract

Use Conventional Commits (`feat(scope): ...`, `fix(scope): ...`, `ci(scope): ...`, `docs(scope): ...`). Every changed commit must have the author's DCO `Signed-off-by: Name <email>` trailer. A DCO trailer is **not** cryptographic signing. For this Skill, use the authorized **Git Signing MCP** when preparing remote changes; inspect its fixed identity and obtain a signed commit with checked base HEAD, then independently verify SHA, signature and DCO identity. Do not claim to sign as a different person.

## Focused PR

- Start from a reviewed HEAD and create a dedicated branch. Preserve unrelated work and refuse stale-base overwrites. Do not force-push or rebase other people's commits without authorization.
- PR description: motivation, scope, design choices and rejected alternatives, sources/policy, exact tests with status, security/licensing implications, migration/rollback, outstanding risks and approvals.
- Keep generated screenshots out of tracked files unless explicitly a product asset; link them from the PR description if requested. Do not expose internal infrastructure or personal data.
- Update the existing PR when the requested scope is the same. Review code, conflict resolution, new CI statuses and approvals; never infer merge-readiness from a green label alone.
- Preserve CODEOWNERS approvals, required checks, resolved conversations and branch recency; ask for independent review. A branch protection bypass is not an implicit user authorization.

## Readiness labels

- **Ready for review**: local required checks executed and pass; remote checks may still be pending; source review required.
- **Ready for merge**: remote mandatory checks on expected SHA pass, approvals/threads/rulesets satisfied, relevant risk documented; never self-merge with this Skill.
- **Blocked**: unavailable dependency, failing check, missing authorization, security/release concern or unverified gates.

Review and approval are separate actions; publish, deploy, ruleset apply and merge require explicit authorization.
