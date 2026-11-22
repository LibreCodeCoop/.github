// SPDX-FileCopyrightText: 2026 LibreCode coop and contributors
// SPDX-License-Identifier: AGPL-3.0-or-later
'use strict'

const { test } = require('node:test')
const assert = require('node:assert/strict')
const { readFileSync } = require('node:fs')
const { join } = require('node:path')

const workflow = readFileSync(join(__dirname, '..', 'workflow-templates', 'command-submodule-pr.yml'), 'utf8')
const marker = '      - name: Resolve source pull request\n'
const start = workflow.indexOf(marker)
assert.ok(start >= 0, 'source PR resolver must exist')
const body = workflow.slice(start + marker.length)
const scriptStart = body.indexOf('          script: |\n')
assert.ok(scriptStart >= 0, 'resolver must use an inline, testable script')
const lines = body.slice(scriptStart + '          script: |\n'.length).split('\n')
const script = []
for (const line of lines) {
  if (!line.startsWith('            ')) break
  script.push(line.slice(12))
}
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor
const resolve = new AsyncFunction('github', 'context', 'core', script.join('\n'))

const HEAD = 'a'.repeat(40)
const MERGED = 'b'.repeat(40)
const standard = {
  state: 'open', merged_at: null, merge_commit_sha: null,
  head: { repo: { full_name: 'LibreSign/3rdparty' }, ref: 'dependabot/composer/stable33/example', sha: HEAD },
  base: { ref: 'stable33' },
}

async function evaluate(overrides = {}) {
  const pr = structuredClone(standard)
  Object.assign(pr, overrides)
  const outputs = {}
  const github = { rest: { pulls: { get: async () => ({ data: pr }) } } }
  try {
    await resolve(github, { repo: { owner: 'LibreSign', repo: '3rdparty' }, issue: { number: 77 } },
      { setOutput: (key, value) => { outputs[key] = value } })
    return { outputs }
  } catch (error) {
    return { error: error.message }
  }
}

test('open source uses its verified HEAD revision', async () => {
  const result = await evaluate()
  assert.equal(result.outputs.source_gitlink_sha, HEAD)
  assert.equal(result.outputs.source_merged, 'false')
  assert.equal(result.outputs.base_ref, 'stable33')
})

test('merged source uses the merge SHA instead of deleted branch HEAD', async () => {
  const result = await evaluate({ state: 'closed', merged_at: '2026-11-22T00:00:00Z', merge_commit_sha: MERGED })
  assert.equal(result.outputs.source_gitlink_sha, MERGED)
  assert.equal(result.outputs.source_merged, 'true')
})

test('fork is never allowed to supply the dependency ref', async () => {
  const result = await evaluate({ head: { ...standard.head, repo: { full_name: 'other/fork' } } })
  assert.match(result.error, /Only source pull requests/)
})

test('unmerged closed source is rejected', async () => {
  const result = await evaluate({ state: 'closed' })
  assert.match(result.error, /closed without being merged/)
})

test('unsupported branch is rejected', async () => {
  const result = await evaluate({ base: { ref: 'stable32-other' } })
  assert.match(result.error, /Unsupported source base/)
})

test('unsafe source ref is rejected', async () => {
  const result = await evaluate({ head: { ...standard.head, ref: '../../override' } })
  assert.match(result.error, /Unsafe source branch/)
})

test('merged PR without merge commit is rejected', async () => {
  const result = await evaluate({ state: 'closed', merged_at: '2026-11-22T00:00:00Z' })
  assert.match(result.error, /lacks a valid merge/)
})

test('invalid HEAD SHA is rejected', async () => {
  const result = await evaluate({ head: { ...standard.head, sha: 'invalid' } })
  assert.match(result.error, /Invalid source pull/)
})

test('merged gitlink is guarded against rollback', () => {
  assert.match(workflow, /compare\/\$\{current_sha\}\.\.\.\$\{SOURCE_GITLINK_SHA\}/)
  assert.match(workflow, /status.*ahead/)
})
