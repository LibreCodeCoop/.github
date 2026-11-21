// SPDX-FileCopyrightText: 2026 LibreCode coop and contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

'use strict'

const fs = require('node:fs')
const path = require('node:path')
const {execFileSync} = require('node:child_process')

const SHA = /^[0-9a-f]{40}$/

function changedPaths(root) {
  const git = args => execFileSync('git', args, {cwd: root, encoding: 'utf8'})
    .split('\0').filter(Boolean)
  return [...new Set([
    ...git(['diff', '--name-only', '--no-renames', '-z', 'HEAD']),
    ...git(['ls-files', '--others', '--exclude-standard', '-z']),
  ])].sort()
}

function validatePaths(paths) {
  if (!Array.isArray(paths) || paths.length > 1000) {
    throw new Error('Unexpected number of generated vendor paths')
  }
  for (const filename of paths) {
    if (typeof filename !== 'string' ||
        !/^composer\/[a-zA-Z0-9_.\/-]+$/.test(filename) ||
        filename.split('/').some(part => part === '.' || part === '..')) {
      throw new Error('Unexpected change outside scoped vendor files: ' + filename)
    }
  }
}

async function commitGeneratedVendor({
  github, context, core, env, root = process.cwd(),
  changed = changedPaths, fsApi = fs,
}) {
  const owner = context.repo.owner
  const repo = context.repo.repo
  const expected = env.SOURCE_HEAD
  const branch = env.HEAD_REF
  const name = env.SIGNER_NAME
  const email = env.SIGNER_EMAIL
  if (!SHA.test(expected || '') ||
      !/^[a-zA-Z0-9_.-]+(?:\/[a-zA-Z0-9_.-]+)*$/.test(branch || '') ||
      !name || /[\r\n<>]/.test(name) ||
      !email || /[\r\n<>\s]/.test(email)) {
    throw new Error('Missing source revision or trusted GitHub App signer')
  }
  const {data: pr} = await github.rest.pulls.get({
    owner, repo, pull_number: context.issue.number,
  })
  if (pr.state !== 'open' || pr.head.repo?.full_name !== owner + '/' + repo ||
      pr.head.ref !== branch || pr.head.sha !== expected ||
      !/^(main|stable\d+)$/.test(pr.base.ref)) {
    throw new Error('The source pull request changed or is not authorized for regeneration')
  }
  const filenames = changed(root)
  validatePaths(filenames)
  if (filenames.length === 0) {
    core.notice('Scoped vendor files already match the dependency lockfile')
    return
  }

  const {data: base} = await github.rest.git.getCommit({
    owner, repo, commit_sha: expected,
  })
  const tree = []
  for (const filename of filenames) {
    const absolute = path.join(root, filename)
    let stat
    try {
      stat = fsApi.lstatSync(absolute)
    } catch (err) {
      if (err.code !== 'ENOENT') throw err
      tree.push({path: filename, mode: '100644', type: 'blob', sha: null})
      continue
    }
    if (!stat.isFile() && !stat.isSymbolicLink()) {
      throw new Error('Unsupported file type: ' + filename)
    }
    const mode = stat.isSymbolicLink() ? '120000' :
      (stat.mode & 0o111 ? '100755' : '100644')
    const content = stat.isSymbolicLink() ?
      Buffer.from(fsApi.readlinkSync(absolute)) : fsApi.readFileSync(absolute)
    if (content.length > 40 * 1024 * 1024) {
      throw new Error('Generated vendor file exceeds GitHub blob limit')
    }
    const {data: blob} = await github.rest.git.createBlob({
      owner, repo, content: content.toString('base64'), encoding: 'base64',
    })
    tree.push({path: filename, mode, type: 'blob', sha: blob.sha})
  }
  const {data: updatedTree} = await github.rest.git.createTree({
    owner, repo, base_tree: base.tree.sha, tree,
  })
  const {data: commit} = await github.rest.git.createCommit({
    owner, repo, tree: updatedTree.sha, parents: [expected],
    message: 'chore(autoloader): Regenerate scoped dependencies\n\n' +
      'Signed-off-by: ' + name + ' <' + email + '>',
  })
  if (commit.verification?.verified !== true ||
      commit.author?.name !== name || commit.author?.email !== email ||
      commit.committer?.email !== email) {
    throw new Error('GitHub App did not verify the signed vendor commit')
  }

  const {data: current} = await github.rest.pulls.get({
    owner, repo, pull_number: context.issue.number,
  })
  if (current.head.sha !== expected) {
    throw new Error('Pull request changed while generating vendor files')
  }
  await github.rest.git.updateRef({
    owner, repo, ref: 'heads/' + branch, sha: commit.sha, force: false,
  })
  core.notice('Pushed verified scoped vendor commit: ' + commit.sha)
}

module.exports = {commitGeneratedVendor, changedPaths, validatePaths}
