// SPDX-FileCopyrightText: 2026 LibreCode coop and contributors
// SPDX-License-Identifier: AGPL-3.0-or-later
'use strict'

const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')
const {commitGeneratedVendor, validatePaths} = require('./commit.js')

const sha = n => n.repeat(40)

function fixture(changes = ['composer/Example.php']) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'librecode-vendor-'))
  fs.mkdirSync(path.join(root, 'composer'))
  fs.writeFileSync(path.join(root, 'composer/Example.php'), '<?php echo 1;')
  const pr = {state: 'open', head: {
    repo: {full_name: 'LibreSign/3rdparty'}, ref: 'dependabot/branch', sha: sha('a'),
  }, base: {ref: 'main'}}
  const calls = []
  const wrap = (name, impl) => async params => {
    calls.push({name, params})
    return {data: impl(params)}
  }
  const signer = {name: 'workflow-bot[bot]', email: '123+workflow-bot[bot]@users.noreply.github.com'}
  const github = {rest: {
    pulls: {get: wrap('pulls.get', () => pr)},
    git: {
      getCommit: wrap('git.getCommit', () => ({tree: {sha: sha('b')}})),
      createBlob: wrap('git.createBlob', () => ({sha: sha('c')})),
      createTree: wrap('git.createTree', () => ({sha: sha('d')})),
      createCommit: wrap('git.createCommit', () => ({
        sha: sha('e'), verification: {verified: true},
        author: signer, committer: {name: 'GitHub', email: 'noreply@github.com'},
      })),
      updateRef: wrap('git.updateRef', () => ({})),
    },
  }}
  const outputs = {}
  const core = {notice() {}, info() {}, setOutput(key, value) { outputs[key] = value }}
  const context = {repo: {owner: 'LibreSign', repo: '3rdparty'}, issue: {number: 77}}
  const env = {SOURCE_HEAD: sha('a'), HEAD_REF: pr.head.ref,
    SIGNER_NAME: signer.name, SIGNER_EMAIL: signer.email}
  const changed = () => changes
  const clean = () => fs.rmSync(root, {recursive: true, force: true})
  return {github, context, core, env, root, changed, calls, pr, clean, outputs}
}

test('creates verified, DCO-compliant, fast-forward-only vendor commit', async () => {
  const f = fixture()
  try {
    await commitGeneratedVendor(f)
    const blob = f.calls.find(c => c.name === 'git.createBlob')
    assert.equal(blob.params.encoding, 'base64')
    assert.equal(Buffer.from(blob.params.content, 'base64').toString(), '<?php echo 1;')
    const tree = f.calls.find(c => c.name === 'git.createTree').params
    assert.deepEqual(tree.tree, [{path: 'composer/Example.php', mode: '100644',
      type: 'blob', sha: sha('c')}])
    const signed = f.calls.find(c => c.name === 'git.createCommit').params
    assert.equal('author' in signed, false)
    assert.equal('committer' in signed, false)
    assert.deepEqual(signed.parents, [sha('a')])
    assert.match(signed.message, /Signed-off-by: workflow-bot\[bot\]/)
    const pushed = f.calls.find(c => c.name === 'git.updateRef').params
    assert.equal(pushed.force, false)
    assert.equal(f.outputs.changed, 'true')
    assert.equal(f.outputs.commit_sha, sha('e'))
  } finally {f.clean()}
})

test('rejects a change outside composer before creating blobs', async () => {
  const f = fixture(['README.md'])
  try {
    await assert.rejects(commitGeneratedVendor(f), /Unexpected change/)
    assert.equal(f.calls.some(c => c.name === 'git.createBlob'), false)
  } finally {f.clean()}
})

test('rejects traversal and malformed changed paths', () => {
  assert.throws(() => validatePaths(['composer/../../secrets']), /Unexpected/)
  assert.throws(() => validatePaths(['composer/../foo']), /Unexpected/)
  assert.throws(() => validatePaths(['vendor/bin']), /Unexpected/)
})

test('rejects an unsigned commit without advancing the ref', async () => {
  const f = fixture()
  f.github.rest.git.createCommit = async () => ({data: {
    sha: sha('e'), verification: {verified: false},
    author: {name: f.env.SIGNER_NAME, email: f.env.SIGNER_EMAIL},
    committer: {email: f.env.SIGNER_EMAIL},
  }})
  try {
    await assert.rejects(commitGeneratedVendor(f), /did not verify/)
    assert.equal(f.calls.some(c => c.name === 'git.updateRef'), false)
  } finally {f.clean()}
})

test('refuses concurrent source head movement', async () => {
  const f = fixture()
  let reads = 0
  f.github.rest.pulls.get = async () => {
    reads += 1
    return {data: reads > 1 ? {...f.pr, head: {...f.pr.head, sha: sha('f')}} : f.pr}
  }
  try {
    await assert.rejects(commitGeneratedVendor(f), /changed while/)
    assert.equal(f.calls.some(c => c.name === 'git.updateRef'), false)
  } finally {f.clean()}
})

test('handles a true no-op without creating commits', async () => {
  const f = fixture([])
  try {
    await commitGeneratedVendor(f)
    assert.equal(f.calls.some(c => c.name === 'git.createCommit'), false)
    assert.equal(f.outputs.changed, 'false')
    assert.equal(f.outputs.commit_sha, '')
  } finally {f.clean()}
})

test('rejects a verified vendor commit when author does not match DCO', async () => {
  const f = fixture()
  f.github.rest.git.createCommit = async () => ({data: {
    sha: sha('e'), verification: {verified: true, reason: 'valid'},
    author: {name: 'another', email: 'another@example.com'},
    committer: {email: 'noreply@github.com'},
  }})
  try {
    await assert.rejects(commitGeneratedVendor(f), /author does not match/)
    assert.equal(f.calls.some(c => c.name === 'git.updateRef'), false)
  } finally {f.clean()}
})

test('unsigned vendor commit reports its GitHub verification reason', async () => {
  const f = fixture()
  f.github.rest.git.createCommit = async () => ({data: {
    sha: sha('e'), verification: {verified: false, reason: 'unsigned'},
    author: {name: f.env.SIGNER_NAME, email: f.env.SIGNER_EMAIL},
  }})
  try {
    await assert.rejects(commitGeneratedVendor(f), /reason: unsigned/)
    assert.equal(f.calls.some(c => c.name === 'git.updateRef'), false)
  } finally {f.clean()}
})
