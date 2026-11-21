// SPDX-FileCopyrightText: 2026 LibreCode coop and contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

'use strict'

const test = require('node:test')
const assert = require('node:assert/strict')
const update = require('./update.js')

const sha = chr => chr.repeat(40)

function fixture(change = () => {}, envChange = {}) {
  const parent = {
    state: 'open',
    head: { repo: {full_name: 'LibreSign/libresign'}, ref: 'deps/upgrade', sha: sha('a') },
    base: {ref: 'main'},
    body: '- [ ] 3rdparty: https://github.com/LibreSign/3rdparty/pull/17',
  }
  const source = {
    merged_at: '2026-11-17T12:00:00Z',
    merge_commit_sha: sha('b'),
    base: {ref: 'main'},
  }
  const gitlink = {path: '3rdparty', mode: '160000', type: 'commit', sha: sha('c')}
  change({parent, source, gitlink})
  const calls = []
  const wrap = (name, fn) => async args => {
    calls.push({name, args})
    return {data: await fn(args)}
  }
  const github = {rest: {
    pulls: {get: wrap('pulls.get', args => args.repo === '3rdparty' ? source : parent)},
    git: {
      getCommit: wrap('git.getCommit', () => ({tree: {sha: sha('d')}})),
      getTree: wrap('git.getTree', () => ({tree: [gitlink]})),
      createTree: wrap('git.createTree', () => ({sha: sha('e')})),
      createCommit: wrap('git.createCommit', () => ({
        sha: sha('f'),
        verification: {verified: true},
        author: {name: 'workflows[bot]', email: '123+workflows[bot]@users.noreply.github.com'},
        committer: {name: 'workflows[bot]', email: '123+workflows[bot]@users.noreply.github.com'},
      })),
      updateRef: wrap('git.updateRef', () => ({})),
    },
    issues: {createComment: wrap('issues.createComment', () => ({}))},
  }}
  const notices = []
  const context = {repo: {owner: 'LibreSign', repo: 'libresign'}, issue: {number: 42}}
  const core = {notice: text => notices.push(text)}
  const env = {
    SUBMODULE_PATH: '3rdparty',
    SOURCE_REPOSITORY: 'LibreSign/3rdparty',
    SUBMODULE_SIGNER_NAME: 'workflows[bot]',
    SUBMODULE_SIGNER_EMAIL: '123+workflows[bot]@users.noreply.github.com',
    ...envChange,
  }
  return {github, context, core, env, calls, notices}
}

test('updates only the gitlink at the exact merged SHA, with DCO and no force push', async () => {
  const f = fixture()
  await update(f)
  const tree = f.calls.find(x => x.name === 'git.createTree').args
  assert.deepEqual(tree.tree, [{path: '3rdparty', mode: '160000', type: 'commit', sha: sha('b')}])
  assert.equal(tree.base_tree, sha('d'))
  const commit = f.calls.find(x => x.name === 'git.createCommit').args
  assert.deepEqual(commit.parents, [sha('a')])
  assert.match(commit.message, /Signed-off-by: workflows\[bot\]/)
  assert.equal('author' in commit, false)
  assert.equal('committer' in commit, false)
  const pushed = f.calls.find(x => x.name === 'git.updateRef').args
  assert.equal(pushed.force, false)
  assert.equal(pushed.ref, 'heads/deps/upgrade')
  assert.equal(f.calls.at(-1).name, 'issues.createComment')
})

const cases = [
  ['fork is rejected', ({parent}) => {parent.head.repo.full_name = 'fork/libresign'}],
  ['closed target is rejected', ({parent}) => {parent.state = 'closed'}],
  ['unsupported target branch is rejected', ({parent}) => {parent.base.ref = 'feature'}],
  ['missing linked source PR is rejected', ({parent}) => {parent.body = ''}],
  ['duplicate linked source PRs are rejected', ({parent}) => {parent.body += '\n' + parent.body}],
  ['unmerged source is rejected', ({source}) => {source.merged_at = null}],
  ['mismatched source branch is rejected', ({source}) => {source.base.ref = 'stable35'}],
  ['unrecognized submodule is rejected', ({gitlink}) => {gitlink.path = 'other'}],
]
for (const [name, change] of cases) {
  test(name, async () => {
    const f = fixture(change)
    await assert.rejects(update(f))
    assert.equal(f.calls.some(x => x.name === 'git.createCommit'), false)
  })
}

test('path traversal is rejected before any API access', async () => {
  const f = fixture(() => {}, {SUBMODULE_PATH: '../3rdparty'})
  await assert.rejects(update(f), /Invalid submodule path/)
  assert.equal(f.calls.length, 0)
})

test('idempotent update does not create commits or comments', async () => {
  const f = fixture(({source, gitlink}) => {gitlink.sha = source.merge_commit_sha})
  await update(f)
  assert.equal(f.calls.some(x => x.name === 'git.createCommit'), false)
  assert.equal(f.calls.some(x => x.name === 'issues.createComment'), false)
  assert.equal(f.notices.length, 1)
})

test('concurrent ref movement rejects without reporting success', async () => {
  const f = fixture()
  f.github.rest.git.updateRef = async () => {
    throw new Error('Reference changed')
  }
  await assert.rejects(update(f), /Reference changed/)
  assert.equal(f.calls.some(x => x.name === 'issues.createComment'), false)
})

test('rejects missing signer metadata before writing to the branch', async () => {
  const f = fixture(() => {}, {SUBMODULE_SIGNER_NAME: ''})
  await assert.rejects(update(f), /signing identity/)
  assert.equal(f.calls.some(x => x.name === 'git.createCommit'), false)
  assert.equal(f.calls.some(x => x.name === 'git.updateRef'), false)
})

test('rejects an unverified GitHub App commit without updating the ref', async () => {
  const f = fixture()
  f.github.rest.git.createCommit = async () => ({data: {
    sha: sha('f'),
    verification: {verified: false},
    author: {name: 'workflows[bot]', email: '123+workflows[bot]@users.noreply.github.com'},
    committer: {email: '123+workflows[bot]@users.noreply.github.com'},
  }})
  await assert.rejects(update(f), /did not verify/)
  assert.equal(f.calls.some(x => x.name === 'git.updateRef'), false)
})

test('rejects a signer identity mismatch even if signature is valid', async () => {
  const f = fixture()
  f.github.rest.git.createCommit = async () => ({data: {
    sha: sha('f'),
    verification: {verified: true},
    author: {name: 'untrusted[bot]', email: 'untrusted@example.com'},
    committer: {email: 'untrusted@example.com'},
  }})
  await assert.rejects(update(f), /did not verify/)
  assert.equal(f.calls.some(x => x.name === 'git.updateRef'), false)
})
