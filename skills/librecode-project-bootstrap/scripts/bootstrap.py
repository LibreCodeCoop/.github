#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 LibreCode Coop and contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Conservative, dependency-free CLI starter for LibreCode engineering experiments.

This is intentionally not a replacement for project-specific architecture,
CI installation, dependency audit, or meaningful production tests.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from datetime import date

YEAR = date.today().year

HERE = Path(__file__).resolve().parent.parent
NAME_RE = re.compile(r"^[a-z][a-z0-9]*(?:[-_][a-z0-9]+)*$")
SPDX_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.+-]*$")
RUNTIME_RE = re.compile(r"^[0-9]+(?:\.[0-9]+){0,2}$")
LANGUAGES = ("php", "python", "javascript", "go")


def source_header(language: str, copyright_holder: str, license_id: str) -> str:
    prefix = "//" if language in {"php", "javascript", "go"} else "#"
    return (
        f"{prefix} SPDX-FileCopyrightText: {YEAR} {copyright_holder}\n"
        f"{prefix} SPDX-License-Identifier: {license_id}\n"
    )


def markdown_header(owner: str, license_id: str) -> str:
    return (
        f"<!-- SPDX-FileCopyrightText: {YEAR} {owner} -->\n"
        f"<!-- SPDX-License-Identifier: {license_id} -->\n\n"
    )


def generic_files(name: str, language: str, runtime: str, license_id: str, owner: str) -> dict[str, str]:
    text = markdown_header(owner, license_id)
    root = {
        "README.md": (
            text + f"# {name}\n\nMinimal {language} CLI starter. Replace the sample CLI "
            "contract with real project behavior before a production release.\n\n"
            f"Runtime: {language} {runtime}. Distribution: source.\n\n"
            "## Verification\n\nSee the language-native test and syntax commands reported by "
            "the bootstrap tool. Do not claim a complete quality gate until static analysis, "
            "CI, dependency/security audits and relevant integration tests have run.\n\n"
            f"## License\n\n{license_id}. See `LICENSES/`.\n"
        ),
        "CONTRIBUTING.md": (
            text + "# Contributing\n\nUse focused pull requests and conventional commit subjects. "
            "Add DCO `Signed-off-by` trailers to commits. Run the project's verification "
            "commands and report status and unresolved checks. Cryptographic signing "
            "and review policies must follow the repository's current governance.\n"
        ),
        ".gitignore": source_header("python", owner, license_id),
    }
    return root


def python_files(name: str, runtime: str, owner: str, license_id: str) -> tuple[dict[str, str], list[str]]:
    module = name.replace("-", "_")
    header = source_header("python", owner, license_id)
    files = {
        f"src/{module}/__init__.py": header + '__version__ = "0.1.0"\n',
        f"src/{module}/__main__.py": (
            header + "from .cli import main\n\nif __name__ == \"__main__\":\n    raise SystemExit(main())\n"
        ),
        f"src/{module}/cli.py": (
            header + "import argparse\n\nfrom . import __version__\n\n\n"
            "def main(args: list[str] | None = None) -> int:\n"
            f"    parser = argparse.ArgumentParser(prog={name!r})\n"
            "    parser.add_argument(\"--version\", action=\"store_true\")\n"
            "    options = parser.parse_args(args)\n"
            "    if options.version:\n"
            f"        print({name!r} + \" \" + __version__)\n"
            "    else:\n        parser.print_help()\n"
            "    return 0\n"
        ),
        "tests/test_cli.py": (
            header + "import contextlib\nimport io\nimport sys\nimport unittest\n"
            "from pathlib import Path\n\n"
            "sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))\n"
            f"from {module}.cli import main\n\n\n"
            "class CliTest(unittest.TestCase):\n"
            "    def test_version_output(self):\n"
            "        output = io.StringIO()\n"
            "        with contextlib.redirect_stdout(output):\n"
            "            self.assertEqual(main(['--version']), 0)\n"
            f"        self.assertEqual(output.getvalue(), {name!r} + ' 0.1.0\\n')\n\n"
            "    def test_rejects_unknown_argument(self):\n"
            "        with contextlib.redirect_stderr(io.StringIO()):\n"
            "            with self.assertRaises(SystemExit) as result:\n"
            "                main(['--invalid'])\n"
            "        self.assertEqual(result.exception.code, 2)\n"
        ),
        "pyproject.toml": (
            source_header("python", owner, license_id)
            + "[build-system]\nrequires = ['setuptools>=75,<81']\n"
            "build-backend = 'setuptools.build_meta'\n\n[project]\n"
            f"name = {name!r}\nversion = '0.1.0'\n"
            f"requires-python = '>={runtime}'\nlicense = {license_id!r}\n"
            "dependencies = []\n\n[tool.setuptools.packages.find]\nwhere = ['src']\n"
        ),
    }
    files[".gitignore"] = header + "__pycache__/\n.venv/\ndist/\n*.egg-info/\n"
    return files, ["python3 -m compileall -q src tests", "python3 -m unittest discover -s tests -v"]


def php_files(name: str, runtime: str, owner: str, license_id: str) -> tuple[dict[str, str], list[str]]:
    namespace = "LibreCode\\" + "".join(s.capitalize() for s in re.split(r"[-_]", name))
    header = source_header("php", owner, license_id)
    open_php = "<?php\ndeclare(strict_types=1);\n" + header + "\n"
    files = {
        "src/Application.php": (
            open_php + f"namespace {namespace};\n\nfinal class Application\n{{\n"
            "    public const VERSION = '0.1.0';\n\n"
            "    public static function run(array $args): int\n    {\n"
            "        if ($args === ['--version']) {\n"
            f"            echo '{name} ' . self::VERSION . PHP_EOL;\n            return 0;\n"
            "        }\n        if ($args !== []) {\n"
            "            fwrite(STDERR, 'Unknown argument' . PHP_EOL);\n            return 2;\n"
            "        }\n"
            f"        echo 'Usage: {name} [--version]' . PHP_EOL;\n        return 0;\n"
            "    }\n}\n"
        ),
        f"bin/{name}.php": (
            open_php + "require dirname(__DIR__) . '/src/Application.php';\n"
            f"exit(\\{namespace}\\Application::run(array_slice($argv, 1)));\n"
        ),
        "tests/run.php": (
            open_php + "require dirname(__DIR__) . '/src/Application.php';\n"
            f"use {namespace}\\Application;\n\n"
            "ob_start();\n"
            "$ok = Application::run(['--version']);\n"
            "$text = ob_get_clean();\n"
            f"if ($ok !== 0 || $text !== '{name} 0.1.0' . PHP_EOL) {{\n"
            "    fwrite(STDERR, 'version behavior failed' . PHP_EOL);\n    exit(1);\n}\n"
            "if (Application::run(['--invalid']) !== 2) {\n"
            "    fwrite(STDERR, 'negative input contract failed' . PHP_EOL);\n    exit(1);\n}\n"
            "echo '2 PHP CLI assertions passed' . PHP_EOL;\n"
        ),
        "tools/lint.php": (
            open_php + "foreach (['src', 'tests', 'bin', 'tools'] as $folder) {\n"
            "    $iterator = new RecursiveIteratorIterator(\n"
            "        new RecursiveDirectoryIterator(dirname(__DIR__) . '/' . $folder)\n"
            "    );\n"
            "    foreach ($iterator as $file) {\n"
            "        if (!$file->isFile() || $file->getExtension() !== 'php') {\n"
            "            continue;\n        }\n"
            "        $cmd = escapeshellarg(PHP_BINARY) . ' -l ' . escapeshellarg($file->getPathname());\n"
            "        exec($cmd, $output, $status);\n"
            "        if ($status !== 0) {\n"
            "            fwrite(STDERR, implode(PHP_EOL, $output) . PHP_EOL);\n"
            "            exit($status);\n        }\n"
            "        $output = [];\n    }\n}\n"
            "echo 'PHP syntax checks passed' . PHP_EOL;\n"
        ),
        "composer.json": json.dumps(
            {
                "name": "librecode/" + name,
                "description": "Minimal CLI bootstrap; replace before release",
                "type": "project",
                "license": license_id,
                "require": {"php": ">=" + runtime},
                "autoload": {"psr-4": {namespace + "\\": "src/"}},
                "scripts": {
                    "lint": "@php tools/lint.php",
                    "test": "@php tests/run.php",
                    "check": ["@lint", "@test"],
                },
                "config": {"sort-packages": True},
            }, indent=2,
        ) + "\n",
    }
    files[".gitignore"] = source_header("python", owner, license_id) + "/vendor/\n/build/\n"
    return files, ["php tools/lint.php", "php tests/run.php"]


def javascript_files(name: str, runtime: str, owner: str, license_id: str) -> tuple[dict[str, str], list[str]]:
    header = source_header("javascript", owner, license_id)
    files = {
        "src/cli.js": (
            header + "export function main(args = process.argv.slice(2), output = console.log) {\n"
            "  if (args.length === 1 && args[0] === '--version') {\n"
            f"    output('{name} 0.1.0');\n    return 0;\n  }}\n"
            "  if (args.length !== 0) return 2;\n"
            f"  output('Usage: {name} [--version]');\n  return 0;\n}}\n"
        ),
        "tests/cli.test.js": (
            header + "import test from 'node:test';\nimport assert from 'node:assert/strict';\n"
            "import { main } from '../src/cli.js';\n\n"
            "test('version', () => {\n  const output = [];\n"
            "  assert.equal(main(['--version'], (x) => output.push(x)), 0);\n"
            f"  assert.deepEqual(output, ['{name} 0.1.0']);\n}});\n"
            "test('rejects unexpected arguments', () => assert.equal(main(['--invalid']), 2));\n"
        ),
        "package.json": json.dumps(
            {"name": name, "version": "0.1.0", "private": True, "type": "module",
             "license": license_id, "engines": {"node": ">=" + runtime},
             "scripts": {"lint:syntax": "node --check src/cli.js", "test": "node --test"}},
            indent=2,
        ) + "\n",
    }
    files[".gitignore"] = source_header("python", owner, license_id) + "/node_modules/\n/coverage/\n"
    return files, ["node --check src/cli.js", "node --test"]


def go_files(name: str, runtime: str, owner: str, license_id: str, module: str) -> tuple[dict[str, str], list[str]]:
    header = source_header("go", owner, license_id)
    files = {
        "go.mod": header + f"module {module}\n\ngo {runtime}\n",
        "main.go": (
            header + "package main\n\nimport (\n\t\"fmt\"\n\t\"os\"\n)\n\n"
            "func run(args []string) int {\n"
            f"\tif len(args) == 1 && args[0] == \"--version\" {{\n\t\tfmt.Println(\"{name} 0.1.0\")\n\t\treturn 0\n\t}}\n"
            "\tif len(args) != 0 {\n\t\treturn 2\n\t}\n"
            f"\tfmt.Println(\"Usage: {name} [--version]\")\n\treturn 0\n}}\n\n"
            "func main() { os.Exit(run(os.Args[1:])) }\n"
        ),
        "main_test.go": (
            header + "package main\n\nimport \"testing\"\n\n"
            "func TestVersion(t *testing.T) { if run([]string{\"--version\"}) != 0 { t.Fatal(\"version\") } }\n"
            "func TestUnexpectedArgs(t *testing.T) { if run([]string{\"--bad\"}) != 2 { t.Fatal(\"negative\") } }\n"
        ),
    }
    files[".gitignore"] = source_header("python", owner, license_id) + "/bin/\n"
    return files, ["gofmt -l .", "go vet ./...", "go test ./..."]


def create(args: argparse.Namespace) -> dict[str, object]:
    name, language, license_id, owner, runtime = args.name, args.language, args.license, args.copyright, args.runtime
    if not NAME_RE.fullmatch(name):
        raise ValueError("name must be lowercase kebab-case or snake_case and start with a letter")
    if not SPDX_RE.fullmatch(license_id):
        raise ValueError("invalid SPDX identifier syntax")
    if not RUNTIME_RE.fullmatch(runtime):
        raise ValueError("runtime must be a numeric version such as 8.3, 3.12, 22 or 1.24")
    if not owner.strip() or "\n" in owner or "\r" in owner:
        raise ValueError("--copyright must identify the project's actual copyright holder")
    if args.kind != "cli" or args.distribution not in {"source", "package"}:
        raise ValueError("the deterministic helper covers CLI/source or CLI/package only; handle other types interactively")
    destination = args.destination.expanduser().absolute()
    if destination.is_symlink() or (destination.exists() and any(destination.iterdir())):
        raise FileExistsError(f"refusing to overwrite existing files: {destination}")
    if destination.exists() and not destination.is_dir():
        raise ValueError(f"destination is not a directory: {destination}")
    if license_id == "MIT" and args.license_file is None:
        license_text = (HERE / "assets/MIT.txt").read_text(encoding="utf-8").replace(
            "Copyright (c) 2026 LibreCode Coop and contributors",
            f"Copyright (c) {YEAR} {owner}",
        )
    elif args.license_file is not None:
        license_text = args.license_file.read_text(encoding="utf-8")
        if len(license_text.strip()) < 100:
            raise ValueError("provided license text looks incomplete")
    else:
        raise ValueError("provide --license-file containing the canonical full license text for non-MIT licenses")
    code = {"python": python_files, "php": php_files, "javascript": javascript_files}
    if language == "go":
        if not args.module or not re.fullmatch(r"[a-zA-Z0-9.-]+(?:/[a-zA-Z0-9._-]+)+", args.module):
            raise ValueError("Go projects require --module with the real module path")
        lang_files, commands = go_files(name, runtime, owner, license_id, args.module)
    else:
        lang_files, commands = code[language](name, runtime, owner, license_id)
    files = generic_files(name, language, runtime, license_id, owner) | lang_files
    files["README.md"] = (
        files["README.md"].replace("Distribution: source.", f"Distribution: {args.distribution}.")
        + "\n## Working local commands\n\n```sh\n"
        + "\n".join(commands) + "\n```\n"
    )
    files[f"LICENSES/{license_id}.txt"] = license_text
    json_like = [p for p in files if p.endswith(".json")]
    reuse_paths = sorted(json_like + [f"LICENSES/{license_id}.txt"])
    files["REUSE.toml"] = (
        f"# SPDX-FileCopyrightText: {YEAR} {owner}\n# SPDX-License-Identifier: {license_id}\n"
        "version = 1\n\n[[annotations]]\n"
        + "path = [" + ", ".join(json.dumps(p) for p in reuse_paths) + "]\n"
        'precedence = "aggregate"\n'
        + "SPDX-FileCopyrightText = " + json.dumps(f"{YEAR} {owner}") + "\n"
        + "SPDX-License-Identifier = " + json.dumps(license_id) + "\n"
    )
    for p in files:
        relative = Path(p)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("generated path escapes destination")
    destination.mkdir(parents=True, exist_ok=True)
    for name, content in sorted(files.items()):
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return {
        "destination": str(destination), "language": language, "runtime": runtime,
        "license": license_id, "files": sorted(files), "commands": commands,
        "pending": [
            "project-specific static analysis/formatter not yet installed or exercised",
            "project-specific integration/security/coverage checks not yet defined",
            "REUSE external lint, vulnerability scanning and license review not yet executed",
            "GitHub CI templates, branch ruleset and CODEOWNERS not yet verified",
            "source-to-release packaging/release authorization not yet verified",
        ],
        "conformance": "NOT_CERTIFIED",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True)
    parser.add_argument("--language", required=True, choices=LANGUAGES)
    parser.add_argument("--runtime", required=True)
    parser.add_argument("--kind", default="cli")
    parser.add_argument("--license", required=True)
    parser.add_argument("--license-file", type=Path)
    parser.add_argument("--copyright", required=True)
    parser.add_argument("--module", help="actual Go module path; mandatory for Go")
    parser.add_argument("--distribution", default="source")
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = create(args)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
