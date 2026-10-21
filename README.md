# LibreCode Coop organization configuration

This repository contains the GitHub organization configuration and automation
used by LibreCode Coop.

LibreCode Coop builds, maintains and supports free software for organizations
that need sustainable technology, open standards and control over their own
infrastructure.

- Services: https://librecode.coop/
- Organization profile: [profile/README.md](profile/README.md)

Technical automation and governance configuration should remain documented in
their dedicated files and repositories.

## Required CI and exceptional merges

The [organization governance configuration](governance.config.json) uses
[github-governance](https://github.com/LibreCodeCoop/github-governance) to
reconcile per-repository rulesets. The first additional CI gates cover
`LibreCodeCoop/release-tool` and `LibreCodeCoop/nextcloud-docker-development`.
The existing `governance-ci` and `organization-config-ci` policies remain in
place. Review and Code Owner requirements are in a separate ruleset. This is
a first rollout, not a requirement on every repository: each project needs
stable PR check names before its CI can be made mandatory.

GitHub auto-merge waits for **required** checks, not every running workflow.
The configured checks are based on actual PR workflows; keep their exact names
in sync if workflows or matrix jobs change. Missing checks block merge.
Organization administrators may bypass this CI ruleset through a pull request
for a justified manual merge. Record the reason in the PR. Build jobs in
`nextcloud-docker-development` may currently fail; this is a real merge gate,
not a reason to silently remove those checks.

To roll out a policy change: review and merge the configuration PR, run the
[governance workflow](.github/workflows/github-governance.yml) with
`apply=false`, check the per-repository plan, then explicitly run with
`apply=true`. Verify the applied ruleset and follow with another dry-run.
Neither merging this configuration nor a scheduled dry-run applies changes.

The current `ruleset-sync` protected environment requires approval even for
scheduled plans. The unattended drift check therefore needs separate work;
do not remove the approval or expose the administration-write App credential
just to make planning unattended.
