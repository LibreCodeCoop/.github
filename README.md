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
reconcile per-repository rulesets. The new shared `required-ci-gate` policy
is selected for `LibreCodeCoop/release-tool` and
`LibreCodeCoop/nextcloud-docker-development`, but is intentionally
**disabled** until both repositories publish and validate `ci-required`.

The CI policy requires exactly one stable check context, `ci-required`,
not a list of matrix/job names. Organization administrators may bypass only
this CI ruleset via a pull request, with the reason documented in the PR.
Review, Code Owner and existing governance/DCO policies remain separate.

### Aggregator contract

A consumer must implement a genuine `ci-required` pull-request check
covering all of its mandatory tests. A final job using `if: always()` and
`needs` can aggregate jobs in a **single workflow**, including reusable
workflows. It cannot inspect jobs in unrelated workflows via `needs`.
If tests remain in independent workflows, a coordinator is required; do
not add a green placeholder or count an unfinished run as successful.

Validate that one failed, cancelled or unexpectedly missing required job
prevents a green `ci-required` result, and that legitimate skipped work is
covered by an explicit contract. Test success, failure, reruns and the
relevant head/merge commit before enabling protection. When adding a
required job, update the aggregator's dependency contract.

The separate [workflow catalog](docs/cross-repository-automation.md)
distributes workflow templates to opt-in consumers through reviewed PRs;
it does not automatically install a new workflow in every repository.

### Controlled rollout

1. Implement and validate the aggregator in each consumer repository.
2. Change `required-ci-gate.enforcement` to `active` in a reviewed PR.
3. Run the [governance workflow](.github/workflows/github-governance.yml)
   with `apply=false` and inspect the plan.
4. Run `apply=true` explicitly, verify each applied ruleset and rerun Plan.

Merging this PR alone does not apply the rulesets or make the disabled CI
gate mandatory. Other repositories and stable branches are outside this
initial opt-in.

The current `ruleset-sync` protected environment requires approval even
for scheduled plans. Unattended drift checking needs separate work; do not
expose the administration-write App credential to remove that approval.
