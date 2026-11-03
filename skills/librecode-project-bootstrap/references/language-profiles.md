<!-- SPDX-FileCopyrightText: 2026 LibreCode Coop and contributors -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Language-specific verification profiles

All commands are **candidates**: select a compatible current toolchain, install it, pin dependencies and run it on a real project. Do not add an unused configuration just because the profile lists a tool. PHP prototypes can run without Composer; that is a first verification stage, **not** a substitute for PHPStan/Psalm and a production test runner.

| Language / use case | Native project setup | Quality and verification | Dependency/distribution |
| --- | --- | --- | --- |
| PHP library/service | `composer.json` PSR-4, supported PHP runtime; choose PHPUnit/Pest as justified | `php -l`; PHPUnit including negative/integration tests; PHPStan **or** Psalm; PHP-CS-Fixer; Composer scripts exposing checks | `composer validate --strict`, `composer install`, `composer audit`; commit `composer.lock` for applications, evaluate lock strategy for libraries |
| Python package/service | `pyproject.toml` and `src/` package, selected Python version | `python -m unittest discover` or pytest; Ruff lint/format and mypy/pyright where needed; `python -m compileall` syntax; integration tests | uv or pip-tools/lock solution selected explicitly, `pip-audit` or equivalent, build and install wheel before publishing |
| TypeScript | `package.json`, `tsconfig.json`, engines and package manager | `npm ci`, `npm run lint`, `npm run check-types`, `npm test`, `npm run build` after defining real scripts; Playwright for UI where justified | `package-lock.json` or project-standard lock, `npm audit`, immutable CI tool versions |
| JavaScript | Explicit Node runtime and module mode | Node `--test`, ESLint/formatter or equivalent; type checking optional for JS | `npm ci`, `npm audit` when dependencies exist |
| Go | `go.mod` and supported Go version | `go test ./...`, `go vet ./...`, `gofmt -l .`, optional `-race` where environment supports | `go mod verify`, `govulncheck` if available; reproducible build |
| Shell/containers | Avoid custom runtime when language-native tooling exists | `shellcheck`, Bats tests for nontrivial scripts, Docker build/smoke, compose validation | Review immutable image tags/digests, vulnerability and secrets scans |
| Other | Choose idiomatic manifest/build tool for that language | Equivalent formatter + static analysis + unit/integration/negative tests, package scan | Lock/pin dependencies, identify supported runtime matrix and release contract |

## Scope-based selection

1. For a **new minimal CLI**, start with a dependency-free language-native smoke/negative test; add a serious test framework and static analyzer once substantive behavior exists. An unused PHPUnit/Ruff/Playwright config is not progress.
2. For a **library**, test both lowest supported runtime/dependencies and supported latest runtime where feasible. For a **deployed service**, add integration, auth/error scenarios, health/readiness and safe migrations.
3. For a **plugin**, reuse host framework conventions and compatibility matrix (e.g. Nextcloud appinfo.xml and supported APIs), without importing host-only workflows into generic code.
4. For **security-sensitive interfaces**, test denial scenarios, tenant isolation, malformed input and transaction guarantees against synthetic fixtures.
5. For a **container image**, build for target architectures, test expected user, persistence, startup/health, and scan dependencies/images. Do not include deployment automation in library scaffolds.
6. Prefer package-manager task aliases (`composer check`, `npm run check`, `go test`) over large shell blocks in GitHub Actions; CI should orchestrate tested commands.

## Local bootstrap helper

`python3 scripts/bootstrap.py --name demo --language python --runtime 3.12 --kind cli --distribution source --copyright "LibreCode Coop and contributors" --destination /tmp/demo` (defaults to AGPL-3.0-or-later; use `--license MIT` only for a deliberate, documented exception)

Supported deterministic minimal CLI stubs: `php`, `python`, `javascript`, `go`; for `typescript` and specialized application types, the Skill must assemble a proper package manifest/test/build via normal engineering work rather than emit an untested incomplete project. Every generated CLI has functional success and negative-argument tests; no production database or deployment infrastructure is added. Report missing third-party lint/static/toolchain checks explicitly until installed and run.
