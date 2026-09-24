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

Rendered downstream templates are declared separately in
`upstream/templates.json`. Each template points to one vendored source, an
ordered patch list and a generated workflow under GitHub's native `workflow-templates/` directory. Template metadata (`*.properties.json`) is maintained locally so LibreCode can provide its own names, descriptions, categories and icons without inheriting upstream branding.

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

The scheduled `refresh-upstream.yml` workflow:

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

A dedicated `WORKFLOW_UPDATE_TOKEN` secret is required for pull-request creation.
Using only the workflow's `GITHUB_TOKEN` would prevent the resulting pull request
from triggering the normal CI workflows. The refresh itself uses the read-only
`GITHUB_TOKEN` to resolve public upstream commits.
