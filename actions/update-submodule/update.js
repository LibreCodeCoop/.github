// SPDX-FileCopyrightText: 2026 LibreCode coop and contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

'use strict'

function validatePath(path) {
  return /^[a-zA-Z0-9_.-]+(\/[a-zA-Z0-9_.-]+)*$/.test(path) &&
    !path.split('/').some(part => part === '.' || part === '..')
}

async function updateSubmodule({ github, context, core, env }) {
  const owner = context.repo.owner
  const repo = context.repo.repo
  const submodule = env.SUBMODULE_PATH
  const sourceRepository = env.SOURCE_REPOSITORY
  if (!validatePath(submodule) ||
      !/^[a-zA-Z0-9_.-]+\/[a-zA-Z0-9_.-]+$/.test(sourceRepository)) {
    throw new Error('Invalid submodule path or source repository configuration')
  }

  const { data: pr } = await github.rest.pulls.get({
    owner, repo, pull_number: context.issue.number,
  })
  if (pr.state !== 'open' ||
      pr.head.repo?.full_name !== owner + '/' + repo ||
      !/^(main|stable\d+)$/.test(pr.base.ref)) {
    throw new Error('Only open, same-repository PRs targeting main or stable are supported')
  }

  const prefix = submodule + ': https://github.com/' + sourceRepository + '/pull/'
  const matches = (pr.body || '').split(/\r?\n/)
    .map(line => line.match(/^\s*-\s*\[[ xX]\]\s*(.*)$/))
    .filter(Boolean)
    .map(match => match[1].trim())
    .filter(text => text.startsWith(prefix))
  if (matches.length !== 1) {
    throw new Error('Expected exactly one linked submodule PR')
  }
  const sourceNumber = matches[0].slice(prefix.length).trim()
  if (!/^[1-9]\d*$/.test(sourceNumber)) {
    throw new Error('Invalid linked submodule PR number')
  }
  const [sourceOwner, sourceName] = sourceRepository.split('/')
  const { data: source } = await github.rest.pulls.get({
    owner: sourceOwner, repo: sourceName, pull_number: Number(sourceNumber),
  })
  if (!source.merged_at || !/^[a-f0-9]{40}$/.test(source.merge_commit_sha || '') ||
      source.base.ref !== pr.base.ref) {
    throw new Error('The linked dependency PR must be merged into the same target branch')
  }

  const { data: commit } = await github.rest.git.getCommit({
    owner, repo, commit_sha: pr.head.sha,
  })
  const { data: currentTree } = await github.rest.git.getTree({
    owner, repo, tree_sha: commit.tree.sha,
  })
  const gitlink = currentTree.tree.find(entry =>
    entry.path === submodule && entry.mode === '160000')
  if (!gitlink) {
    throw new Error('The configured path is not a git submodule')
  }
  if (gitlink.sha === source.merge_commit_sha) {
    core.notice('Submodule already references the merged dependency')
    return
  }

  const signerName = env.SUBMODULE_SIGNER_NAME
  const signerEmail = env.SUBMODULE_SIGNER_EMAIL
  if (!signerName || /[\r\n<>]/.test(signerName) ||
      !signerEmail || /[\r\n<>\s]/.test(signerEmail)) {
    throw new Error('A trusted GitHub App signing identity is required')
  }
  const { data: tree } = await github.rest.git.createTree({
    owner, repo, base_tree: commit.tree.sha,
    tree: [{ path: submodule, mode: '160000', type: 'commit',
      sha: source.merge_commit_sha }],
  })
  const subject = 'chore(deps): update ' + submodule +
    ' from merged PR #' + sourceNumber
  const message = subject + '\n\nSigned-off-by: ' +
    signerName + ' <' + signerEmail + '>'
  // GitHub signs commits created without explicit author/committer when
  // authenticated with a GitHub App installation token.
  const { data: updated } = await github.rest.git.createCommit({
    owner, repo, message, tree: tree.sha, parents: [pr.head.sha],
  })
  if (updated.verification?.verified !== true ||
      updated.author?.name !== signerName ||
      updated.author?.email !== signerEmail ||
      updated.committer?.email !== signerEmail) {
    throw new Error('GitHub did not verify the signer identity; refusing to update the branch')
  }
  await github.rest.git.updateRef({
    owner, repo, ref: 'heads/' + pr.head.ref, sha: updated.sha, force: false,
  })
  await github.rest.issues.createComment({
    owner, repo, issue_number: context.issue.number,
    body: 'Updated ' + submodule + ' to ' + sourceRepository + '#' +
      sourceNumber + ' (' + source.merge_commit_sha + ').',
  })
}

module.exports = updateSubmodule
