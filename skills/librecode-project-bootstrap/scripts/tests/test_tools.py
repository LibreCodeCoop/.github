# SPDX-FileCopyrightText: 2026 LibreCode Coop and contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))
from audit_project import evaluate, inspect_workflow  # noqa: E402
from check_ci_results import check_results  # noqa: E402


def run(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=False, timeout=90)


class BootstrapTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="librecode-bootstrap-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def generate(self, language: str, runtime: str, name: str = "demo-project") -> tuple[Path, dict]:
        directory = self.root / language
        proc = run(
            sys.executable, str(SCRIPT_DIR / "bootstrap.py"),
            "--name", name, "--language", language, "--runtime", runtime,
            "--license", "MIT", "--copyright", "Sample Project contributors",
            "--kind", "cli", "--distribution", "source", "--destination", str(directory),
            *( ["--module", "example.org/" + name] if language == "go" else [] ),
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return directory, json.loads(proc.stdout)

    def test_python_cli_and_negative_test(self):
        project, summary = self.generate("python", "3.11")
        self.assertEqual(summary["conformance"], "NOT_CERTIFIED")
        import tomllib
        self.assertEqual(tomllib.loads((project / "pyproject.toml").read_text())["project"]["license"], "MIT")
        self.assertEqual(run(sys.executable, "-m", "compileall", "-q", "src", "tests", cwd=project).returncode, 0)
        tests = run(sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v", cwd=project)
        self.assertEqual(tests.returncode, 0, tests.stderr)
        self.assertIn("test_rejects_unknown_argument", tests.stderr)
        self.assertFalse((project / "Dockerfile").exists())
        self.assertEqual(evaluate(project)["summary"]["FAIL"], 0)

    @unittest.skipUnless(shutil.which("php"), "PHP is not installed")
    def test_php_cli_and_negative_test(self):
        project, summary = self.generate("php", "8.2")
        self.assertTrue((project / "composer.json").is_file())
        self.assertEqual(json.loads((project / "composer.json").read_text())["license"], "MIT")
        lint = run("php", "tools/lint.php", cwd=project)
        self.assertEqual(lint.returncode, 0, lint.stdout + lint.stderr)
        tests = run("php", "tests/run.php", cwd=project)
        self.assertEqual(tests.returncode, 0, tests.stdout + tests.stderr)
        self.assertIn("2 PHP CLI assertions passed", tests.stdout)
        self.assertIn("php tests/run.php", summary["commands"])
        self.assertFalse((project / "docker-compose.yml").exists())
        self.assertEqual(evaluate(project)["summary"]["FAIL"], 0)

    @unittest.skipUnless(shutil.which("node"), "Node is not installed")
    def test_node_cli(self):
        project, _ = self.generate("javascript", "22")
        self.assertEqual(run("node", "--check", "src/cli.js", cwd=project).returncode, 0)
        tests = run("node", "--test", cwd=project)
        self.assertEqual(tests.returncode, 0, tests.stdout + tests.stderr)

    @unittest.skipUnless(shutil.which("go"), "Go is not installed")
    def test_go_cli(self):
        project, _ = self.generate("go", "1.23")
        self.assertEqual(run("go", "vet", "./...", cwd=project).returncode, 0)
        tests = run("go", "test", "./...", cwd=project)
        self.assertEqual(tests.returncode, 0, tests.stdout + tests.stderr)

    def test_refuses_to_overwrite_existing_files(self):
        project = self.root / "existing"
        project.mkdir()
        (project / "README.md").write_text("keep", encoding="utf-8")
        proc = run(sys.executable, str(SCRIPT_DIR / "bootstrap.py"),
                   "--name", "demo", "--language", "python", "--runtime", "3.12",
                   "--license", "MIT", "--copyright", "Sample Project",
                   "--destination", str(project))
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual((project / "README.md").read_text(), "keep")

    def test_does_not_infer_non_mit_license_text(self):
        proc = run(sys.executable, str(SCRIPT_DIR / "bootstrap.py"),
                   "--name", "demo", "--language", "python", "--runtime", "3.12",
                   "--license", "AGPL-3.0-or-later", "--copyright", "Sample Project",
                   "--destination", str(self.root / "missing-license"))
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("--license-file", proc.stderr)
        self.assertFalse((self.root / "missing-license").exists())


class AuditTest(unittest.TestCase):
    def test_detects_unsafe_workflow(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "ci.yml"
            path.write_text("name: Test\npermissions: write-all\nsteps:\n  - uses: actions/checkout@v4\n", encoding="utf-8")
            observations = inspect_workflow(path, root)
            self.assertEqual(len([a for a in observations if a.status == "FAIL"]), 2)
            self.assertIn("workflow-immutable-uses", [a.id for a in observations])

    def test_accepts_pinned_action_with_credential_hardening(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "ci.yml"
            path.write_text("steps:\n  - uses: actions/checkout@" + "a" * 40 +
                            " # v7.0.1\n    with:\n      persist-credentials: false\n", encoding="utf-8")
            self.assertEqual(inspect_workflow(path, root), [])


class AggregateContractTest(unittest.TestCase):
    def test_passing_required_jobs(self):
        self.assertEqual(check_results(["build", "unit"], {"build": {"result": "success"}, "unit": {"result": "success"}}), [])

    def test_failure_cancellation_skip_and_missing_block(self):
        for value in ["failure", "cancelled", "skipped", "pending", "in_progress"]:
            with self.subTest(result=value):
                self.assertTrue(check_results(["unit"], {"unit": {"result": value}}))
        self.assertTrue(check_results(["unit"], {}))
        self.assertTrue(check_results(["unit"], {"unit": {"result": "garbage"}}))

    def test_only_explicitly_allowed_skips_are_accepted(self):
        actual = {"unit": {"result": "success"}, "optional-platform": {"result": "skipped"}}
        self.assertEqual(check_results(["unit", "optional-platform"], actual, {"optional-platform"}), [])
        self.assertTrue(check_results(["unit", "optional-platform"], actual))

    def test_duplicate_required_jobs_rejected(self):
        with self.assertRaises(ValueError):
            check_results(["unit", "unit"], {"unit": {"result": "success"}})


if __name__ == "__main__":
    unittest.main()
