# Homebrew Standalone Binary Distribution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build, package, and release self-contained native binaries for `postgres-mcp` across macOS and Linux, and automate formula/cask updates in `Diaszano/homebrew-tap`.

**Architecture:** A build script packages `postgres-mcp` using PyInstaller into standalone executables for 4 target architectures (`darwin_arm64`, `darwin_amd64`, `linux_amd64`, `linux_arm64`), generates `.tar.gz` bundles with checksums, attaches them to GitHub Releases, and updates the `postgres-mcp` Cask in `Diaszano/homebrew-tap`.

**Tech Stack:** Python 3.13, PyInstaller, uv, GitHub Actions matrix runners, Homebrew Ruby Cask/Formula syntax.

**Spec:** [homebrew-standalone-binary-design.md](file:///home/diaszano/.gemini/antigravity-cli/brain/f6a3f16a-61b5-4d5b-b86e-6c8c1e63bd05/homebrew-standalone-binary-design.md)

---

## Global Constraints
- Target platform binaries: `darwin_arm64`, `darwin_amd64`, `linux_amd64`, `linux_arm64`.
- Binary naming and archive format: `postgres-mcp_${VERSION}_${OS}_${ARCH}.tar.gz` containing executable `postgres-mcp`.
- Follow Conventional Commits and branch naming conventions for all repository changes.
- Ensure all CI gates remain green (Ruff formatting with `force-single-line = true`, Pyright, pytest suites).
- Homebrew Cask format must match `Diaszano/homebrew-tap/Casks/bearm.rb` conventions.

## Review Focus
1. Entrypoint execution: Standalone binary must run `postgres-mcp --help` without missing hidden imports (`psycopg`, `pglast`, `mcp`, `instructor`).
2. Architecture matching: Archive filenames and sha256 checksums must correctly match macOS Apple Silicon/Intel and Linux x86_64/ARM64.
3. Release idempotency: The binary build workflow must run reliably on release publication without failing if a release tag already exists.
4. Security and immutability: Checksums must be computed directly from final built archives and verified.
5. Homebrew Tap token permissions: Updating `Diaszano/homebrew-tap` requires a secret token (`HOMEBREW_TAP_TOKEN` or `GH_PAT`) and must fail gracefully with clear instructions if unconfigured.

---

### Task 1: Package Entrypoint & Standalone Build Script

**Files:**
- Create: `src/postgres_mcp/__main__.py`
- Create: `scripts/release/build_binary.sh`
- Test: `tests/release/test_binary_build_script.py`

- [ ] **Step 1.1**: Create `src/postgres_mcp/__main__.py` exposing CLI entrypoint:
  ```python
  from postgres_mcp import main

  if __name__ == "__main__":
      main()
  ```
- [ ] **Step 1.2**: Write unit test `tests/release/test_binary_build_script.py` verifying `build_binary.sh` syntax, flags, collected modules (`postgres_mcp`, `psycopg`, `pglast`), and `--onefile` packaging.
- [ ] **Step 1.3**: Implement `scripts/release/build_binary.sh` to package with PyInstaller and create `${NAME}_${VERSION}_${OS}_${ARCH}.tar.gz` along with `sha256` checksum.
- [ ] **Step 1.4**: Run pytest, ruff format/check, and verify script passes.
- [ ] **Step 1.5**: Commit changes: `feat(release): add standalone binary packaging script and module entrypoint`.

---

### Task 2: GitHub Actions Multi-OS Matrix Workflow for Binary Releases

**Files:**
- Create: `.github/workflows/binaries.yml`
- Test: `tests/release/test_binaries_workflow.py`

- [ ] **Step 2.1**: Write test `tests/release/test_binaries_workflow.py` verifying `.github/workflows/binaries.yml` schema, release trigger, matrix platforms (`macos-latest`, `macos-13`, `ubuntu-latest`, `ubuntu-24.04-arm`), and artifact upload.
- [ ] **Step 2.2**: Implement `.github/workflows/binaries.yml` with:
  - Trigger: `release: [published]` or `workflow_dispatch`.
  - Matrix runner jobs for `darwin_arm64`, `darwin_amd64`, `linux_amd64`, `linux_arm64`.
  - Build step calling `scripts/release/build_binary.sh`.
  - Step uploading `.tar.gz` and `.sha256` files directly to the GitHub Release using `gh release upload`.
- [ ] **Step 2.3**: Run pytest and ruff check on new files.
- [ ] **Step 2.4**: Commit changes: `ci(release): add multi-os matrix workflow for standalone binaries`.

---

### Task 3: Homebrew Tap Cask Definition & Tap Dispatcher

**Files:**
- Create: `scripts/release/update_homebrew_tap.py`
- Test: `tests/release/test_homebrew_tap_update.py`

- [ ] **Step 3.1**: Write test `tests/release/test_homebrew_tap_update.py` validating that the generated Ruby Cask matches `Diaszano/homebrew-tap/Casks/bearm.rb` structure, contains correct version, URLs, livecheck, and binary stanza.
- [ ] **Step 3.2**: Implement `scripts/release/update_homebrew_tap.py`:
  - Fetches the SHA256 hashes of the release archives (`darwin_amd64`, `darwin_arm64`, `linux_amd64`, `linux_arm64`).
  - Generates `Casks/postgres-mcp.rb`.
  - If `HOMEBREW_TAP_TOKEN` is present, clones/updates `Diaszano/homebrew-tap` and pushes commit: `chore(release): update postgres-mcp to v<version>`.
  - If token is not present, writes file to `dist/postgres-mcp.rb` and logs instructions for manual push.
- [ ] **Step 3.3**: Add job to `.github/workflows/binaries.yml` that runs after binary uploads to call `scripts/release/update_homebrew_tap.py`.
- [ ] **Step 3.4**: Run full test suite and lint checks.
- [ ] **Step 3.5**: Commit changes: `feat(release): automate homebrew tap cask generation and dispatch`.

---

### Task 4: End-to-End Verification & Initial Cask for `v0.4.2`

**Files:**
- Generate local test binary and verify `./dist/postgres-mcp --help`.
- Generate `Casks/postgres-mcp.rb` for existing release `v0.4.2` to be committed to `Diaszano/homebrew-tap`.
- Test: Full unit and release test suite.

- [ ] **Step 4.1**: Build local Linux binary using `build_binary.sh` and verify execution (`./dist/postgres-mcp --help`).
- [ ] **Step 4.2**: Run full local test suite `pytest tests/unit tests/release` to ensure zero regressions.
- [ ] **Step 4.3**: Push changes to `main`.
- [ ] **Step 4.4**: Provide user with `Casks/postgres-mcp.rb` ready to be committed to `Diaszano/homebrew-tap` or automatically pushed.
