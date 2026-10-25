# Contributing to postgres-mcp

Thank you for your interest in contributing to `postgres-mcp`! We welcome contributions that maintain high engineering standards, security guarantees, and reproducible automation.

---

## 1. Development Principles

- **Test-Driven Development (TDD)**: Every non-trivial behavior or bugfix starts with a failing automated test (RED), followed by the minimal implementation to pass (GREEN), and disciplined refactoring.
- **Simplicity & Safety (Ponytail / YAGNI)**: Favor straightforward, readable code and standard library features over unnecessary abstractions or heavy dependencies.
- **Security & Integrity**: Never hardcode secrets, passwords, or production credentials. Keep SQL injection defenses and query validation strict.

---

## 2. Branch Naming Conventions

All working branches must follow the structured category naming convention:

`<category>/<short-description>`

Allowed categories:
- `feature/`: New features or capabilities (e.g., `feature/query-pagination`)
- `bugfix/`: Non-critical bug fixes (e.g., `bugfix/pool-connection-leak`)
- `hotfix/`: Critical fixes targeting production defects immediately
- `docs/`: Documentation additions and improvements
- `test/`: Adding or improving test suites
- `ci/`: CI/CD workflow, runner, or automation script changes
- `build/`: Packaging, dependency management, or build configuration
- `perf/`: Performance optimizations
- `refactor/`: Refactoring code without altering external behavior
- `chore/`: Routine maintenance tasks

Automated dependency branches created by bot tools must use `dependabot/...`.

---

## 3. Commit Message Conventions

Commit messages must strictly follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:

`<type>(<optional-scope>): <description>`

Allowed types:
- `feat`: Introduces a new user-facing or API feature
- `fix`: Patches a bug
- `docs`: Documentation only changes
- `test`: Adding or modifying tests
- `ci`: CI configuration and automation scripts
- `build`: Dependency updates, build tools, packaging
- `perf`: Code change that improves performance
- `refactor`: Code change that neither fixes a bug nor adds a feature
- `chore`: Maintenance tasks, meta files
- `revert`: Reverts a prior commit

Breaking changes must indicate breaking impact using `!` immediately preceding the colon (e.g., `feat(api)!: remove deprecated flags`) and document the breaking change in the footer.

---

## 4. Pull Request & Merge Policy

1. **Pull Request Template**: Fill out all sections in the pull request template.
2. **Automated Verification**: Ensure all tests, linters, and type checks pass locally:
   ```bash
   uv run pytest -q tests/unit tests/release
   uv run ruff check .
   uv run ruff format --check .
   ```
3. **Squash Merge Strategy**: All pull requests are integrated into `main` using **Squash and Merge**. This ensures that each feature or fix represents a clean, atomic commit with semantic history on the mainline.
4. **Code Ownership & Review**: Critical paths (`.github/workflows/`, `scripts/ci/`, `pyproject.toml`) require approval from maintainers designated in [`.github/CODEOWNERS`](.github/CODEOWNERS).

---

## 5. Automated Dependency Updates (Dependabot)

- Dependabot is configured via [`.github/dependabot.yml`](.github/dependabot.yml) to generate weekly update pull requests for:
  - Python / uv dependencies (`package-ecosystem: uv`)
  - GitHub Actions reusable workflows and actions (`package-ecosystem: github-actions`)
  - Docker base images (`package-ecosystem: docker`)
- Automated dependency branches follow `dependabot/<ecosystem>/<package>-<version>`.
- All Dependabot pull requests require full CI test suite verification and maintainer review before merging.
