# SPDX-FileCopyrightText: 2026 LibreCode coop and contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Contracts for the inherited submodule command workflows."""

import hashlib
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

from scripts.render_upstream import check, load_templates

ROOT = Path(__file__).resolve().parents[1]


class SubmoduleCommandTest(unittest.TestCase):
    def test_upstream_provenance_and_rendering(self) -> None:
        manifest = json.loads((ROOT / "upstream/sources.json").read_text())
        expected = {
            "nextcloud-command-submodule-pr": "nextcloud/3rdparty",
            "nextcloud-command-update-submodule": "nextcloud/server",
        }
        for name, repo in expected.items():
            with self.subTest(name=name):
                item = next(x for x in manifest["sources"] if x["name"] == name)
                self.assertEqual(item["repository"], repo)
                self.assertRegex(item["url"], r"/[0-9a-f]{40}/")
                source = (ROOT / item["destination"]).read_bytes()
                self.assertEqual(hashlib.sha256(source).hexdigest(), item["sha256"])
        check(load_templates(ROOT / "upstream/templates.json"), ROOT)

    def test_no_publish_secrets_during_dependency_analysis_or_staging(self) -> None:
        source = (ROOT / "workflow-templates/command-submodule-pr.yml").read_text()
        process = source.split("  process:\n", 1)[1]
        before_publish = process.split(
            "      - name: Push branch and create target pull request", 1
        )[0]
        self.assertNotIn("secrets.COMMAND_BOT_PAT", before_publish)
        self.assertIn("composer diff --with-links", before_publish)
        self.assertIn("persist-credentials: false", before_publish)
        self.assertIn("gh auth setup-git", process)

        updater = (ROOT / "workflow-templates/command-update-submodule.yml").read_text()
        before_publish = updater.split(
            "      - name: Push updated reference and comment", 1
        )[0]
        self.assertNotIn("secrets.COMMAND_BOT_PAT", before_publish)
        self.assertIn('git read-tree "$HEAD_SHA^{tree}"', before_publish)
        self.assertIn("commit-tree", before_publish)
        self.assertIn("Signed-off-by: github-actions[bot]", before_publish)
        self.assertNotIn("checkout --detach", before_publish)
        self.assertIn("persist-credentials: false", before_publish)
        self.assertNotIn("force-with-lease", updater)
        self.assertIn("ref: $" + "{{ github.event.repository.default_branch }}", updater)

    @staticmethod
    def resolver() -> str:
        lines = (ROOT / "workflow-templates/command-update-submodule.yml").read_text().splitlines()
        start = lines.index("          script: |") + 1
        script = []
        for line in lines[start:]:
            if line and not line.startswith("            "):
                break
            script.append(line[12:] if line else "")
        return "\n".join(script)

    def test_linked_source_pr_authorization_cases(self) -> None:
        if not shutil.which("node"):
            self.skipTest("Node.js unavailable")
        js = "const code = " + json.dumps(self.resolver()) + ";\n" + r"""
const assert = require('node:assert/strict');
const runScript = new Function('github', 'context', 'core', 'process',
  'return (async () => {\n' + code + '\n})();');
async function runCase(name, ok, edit = () => {}, path = '3rdparty') {
  const parent = {state: 'open', body: '- [ ] 3rdparty: https://github.com/LibreSign/3rdparty/pull/17',
    head: {ref: 'deps/update', sha: 'a'.repeat(40),
      repo: {full_name: 'LibreSign/libresign'}}, base: {ref: 'main'}};
  const source = {merged_at: '2026-11-17T12:00:00Z',
    merge_commit_sha: 'b'.repeat(40), base: {ref: 'main'}};
  edit(parent, source);
  const outputs = {};
  const github = {rest: {pulls: {get: async (args) => ({
    data: args.repo === '3rdparty' ? source : parent
  })}}};
  const context = {repo: {owner: 'LibreSign', repo: 'libresign'}, issue: {number: 33}};
  const core = {setOutput: (k, v) => { outputs[k] = v; }};
  const process = {env: {SUBMODULE_PATH: path, SOURCE_REPOSITORY: 'LibreSign/3rdparty'}};
  let err;
  try { await runScript(github, context, core, process); } catch (e) { err = e; }
  assert.equal(!Boolean(err), ok, name + ': ' + err);
  if (ok) {
    assert.equal(outputs.merge_sha, 'b'.repeat(40));
    assert.equal(outputs.source_pr, '17');
  } else {
    assert.deepEqual(outputs, {});
  }
}
(async () => {
  await runCase('valid', true);
  await runCase('checked link', true, p => p.body = p.body.replace('[ ]', '[x]'));
  await runCase('fork', false, p => p.head.repo.full_name = 'fork/libresign');
  await runCase('closed', false, p => p.state = 'closed');
  await runCase('wrong target', false, p => p.base.ref = 'feature');
  await runCase('not merged', false, (p,s) => s.merged_at = null);
  await runCase('branch mismatch', false, (p,s) => s.base.ref = 'stable35');
  await runCase('no link', false, p => p.body = '');
  await runCase('duplicate', false, p => p.body += '\n' + p.body);
  await runCase('wrong source', false, p =>
    p.body = p.body.replace('LibreSign/3rdparty', 'another/3rdparty'));
  await runCase('unsafe path', false, () => {}, '../3rdparty');
  console.log('11 resolver cases passed');
})().catch(e => { console.error(e); process.exitCode = 1; });
"""
        result = subprocess.run(
            ["node", "-e", js], check=False, capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("11 resolver cases passed", result.stdout)


if __name__ == "__main__":
    unittest.main()
