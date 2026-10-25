<!--
SPDX-FileCopyrightText: 2026 LibreCode coop and contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Upstream workflow model

Upstream files are declared in `upstream/sources.json`.

Each entry contains:

- `name`: stable local identifier;
- `repository`, `ref` and `path`: optional tracking metadata used only to discover newer upstream revisions;
- `url`: raw file URL pinned to an immutable upstream commit;
- `sha256`: expected SHA-256 of the downloaded bytes;
- `destination`: repository-relative vendored destination.

The tracking ref can be mutable. The effective source cannot: after refresh, the
manifest is rewritten to a full commit SHA and content hash before the vendored
file is accepted.

The Nextcloud App Store publication template is **LibreCode-owned**:
`workflow-templates/appstore-build-publish.yml` is deliberately not in the
render manifest. We retain Nextcloud's version under `upstream/vendor/` for
review and provenance, but never regenerate our small publication wrapper from
it. Changes to the upstream App Store workflow must be evaluated manually.

Rendered downstream templates are declared separately in
`upstream/templates.json`. Each template points to one vendored source, an
ordered patch list and a generated workflow under GitHub's native `workflow-templates/` directory. Template metadata (`*.properties.json`) is maintained locally so LibreCode can provide its own names, descriptions, categories and icons without inheriting upstream branding.

## Dependency-audit workflow

The `npm-audit-fix.yml` catalog template is derived from a pinned Nextcloud source
using `patches/nextcloud/npm-audit-fix.yml.patch`. The vendored source remains
unaltered. The patch removes Nextcloud-specific release-freeze and automatic
approval/merge behavior, replaces the personal PAT with a short-lived, narrowly
scoped LibreCode GitHub App token, and emits conventional dependency PR titles.

The shared template handles the default branch only. A consumer that audits
supported stable branches supplies `.github/workflows/npm-audit-fix.yml.patch`,
which declares those branches and any local schedule or labels. Do not put
consumer release branches into the shared patch.

To adopt an existing local workflow, first commit the exact rendered
catalog template plus its consumer patch. Otherwise the synchronizer will
correctly report local divergence rather than overwrite the existing file.
After the organization catalog PR is merged, a synchronization PR can record
the catalog revision in `.github/actions-lock.txt`. Verify that the next
synchronization is unchanged. No merge or publication is automatic.

## Commands

Synchronize declared immutable sources:

```bash
python3 scripts/sync_upstream.py sync upstream/sources.json
```

Verify committed vendored files without modifying them:

```bash
python3 scripts/sync_upstream.py check upstream/sources.json
```

Resolve tracked refs to their latest commit, recompute SHA-256 and update the
vendored files:

```bash
python3 scripts/sync_upstream.py refresh upstream/sources.json
```

Render vendored workflows with downstream patches:

```bash
python3 scripts/render_upstream.py sync upstream/templates.json
```

The renderer processes every declared template. Successful templates are updated.
If one or more patches no longer apply, those templates are left unchanged and
the renderer returns a structured report containing every failure.

## Automated refresh

The scheduled (or manually dispatched) `upstream-refresh.yml` workflow:

1. resolves each tracked upstream workflow to its latest commit;
2. updates the immutable URL, SHA-256 and vendored bytes;
3. verifies the vendored sources;
4. attempts every downstream patch;
5. runs the test suite;
6. opens one pull request containing the upstream and successfully rendered changes.

If all patches apply, the pull request is normal. If any patch fails, the pull
request is opened as draft and its body lists each failed template, patch path and
error. The generated template for a failed patch remains at its previous known-good
version. The workflow then fails after creating the pull request so the problem is
also visible in Actions.

Failures while resolving, downloading or verifying upstream sources are treated
as fatal and do not create a partial update pull request.

Pull-request creation uses a short-lived installation token from the `LibreCode Workflow Automation` GitHub App. Using only the workflow's `GITHUB_TOKEN` would prevent the resulting pull request from triggering the normal CI workflows. The refresh itself uses the read-only `GITHUB_TOKEN` only to resolve public upstream commits.

Action pins in rendered templates are intentionally preserved from the current LibreCode template when the same Action still exists upstream. Dependency version updates are owned by Dependabot in this repository, while the upstream refresh imports structural workflow changes. This keeps upstream tracking and dependency updates independently reviewable.

## Keeping refresh pull requests reviewable

Review the three layers independently: pinned upstream sources and hashes,
downstream `.patch` files, and consumer templates. Upstream vendor files must
remain byte-for-byte identical to their pinned source. Do not update only a
rendered consumer template: the next refresh would overwrite that change.

If a patch no longer applies, adjust the minimum relevant hunks and verify that
the rendered output preserves LibreCode's behavior. Do not replace large patches
with autogenerated equivalent diffs solely to satisfy context offsets; avoid
formatting-only changes in generated YAML. When upstream changes only a
dependency pin, keep locally managed pin updates independent from structural
refreshes.

Run:

```bash
python3 scripts/sync_upstream.py check upstream/sources.json
python3 scripts/render_upstream.py check upstream/templates.json
python3 -m unittest discover -s tests
git diff --stat
git diff --ignore-all-space -- workflow-templates/ patches/nextcloud/
```

The automatic refresh runs weekly or through `workflow_dispatch`. It does
not run on every push to `main`; a push-based refresh after its own merge
would otherwise generate avoidable work and potentially immediate new PRs.
