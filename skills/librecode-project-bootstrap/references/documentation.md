<!-- SPDX-FileCopyrightText: 2026 LibreCode Coop and contributors -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Documentation and licensing

Generate only material needed for the project's distribution and operating model:

| Document | Default | Acceptance criteria |
| --- | --- | --- |
| `README.md` | yes | Objective, install/preconditions, exact working test commands, supported runtime, license, support and run instructions |
| `CONTRIBUTING.md` | yes for collaborative repo | DCO and Conventional Commits, review/testing expectations and practical setup |
| `SECURITY.md` | public or security-sensitive projects | Private reporting channel actually owned, scope, no promised SLA without agreement |
| `LICENSES/<id>.txt`, SPDX and `REUSE.toml` | if REUSE adopted | Correct canonical license text and file attribution; `reuse lint` passes |
| `docs/architecture.md` | multiple services/trust boundaries | System ownership, boundaries and significant tradeoffs, not speculative diagrams |
| `docs/development.md` | non-obvious dev setup | All reproducible tool/fixture commands |
| `docs/operations.md` | deployed service | Configuration, secrets handling, health, logs, backups, rollback and responsibilities |
| `CHANGELOG.md` | public versioned releases | Entries reflect actual releases, not a generated history |
| Examples/API specs | if exposed API/SDK | Executable examples, minimal synthetic fixtures, no production URLs/records |

## Licensing decisions

- For new LibreCode-owned projects, default to **AGPL-3.0-or-later**, consistently with the institutionally stated policy and observed licensing. An explicitly requested different SPDX license remains possible after recording the rationale, rights-holder approval and dependency/distribution compatibility. Do not silently relicense an existing project or claim this preference is an enforced GitHub ruleset.
- Verify legal compatibility of dependency licenses, assets and distribution method. Do not invent a new license from a short SPDX string.
- For code/text supporting comments use `SPDX-FileCopyrightText` and `SPDX-License-Identifier`; for JSON/binary files supply `REUSE.toml` annotations or `.license` files. Keep complete canonical license texts in `LICENSES/`. Validate with `reuse lint`, not mere existence checks.
- Existing `LibreCodeCoop/.github` content is licensed AGPL-3.0-or-later; the Skill source follows the same notices. New LibreCode consumer output uses AGPL-3.0-or-later by default and a different license only when deliberately selected and reviewed. Preserve existing licenses in audit mode.

## Avoid ephemeral noise

Do not commit temporary incident logs, one-off investigation notes, screenshots generated for code review, giant audit dumps or per-PR plans that belong in the PR description or private workspace. Document durable behavior, constraints and decisions. Keep PR descriptions current rather than leaving many contradictory progress comments. Prefer reproducible tests and brief explanations over raw command transcripts. Avoid putting machine hostnames, operational IPs or tenant-specific data into public documentation.
