#!/usr/bin/env just --justfile
set shell := ["bash", "-cu"]
set fallback

default:
  just --list

lint:
  uv run ruff check .
  uv run ruff format --check .

typecheck:
  uv run pyright

test-unit:
  uv run pytest -q tests/unit

test-integration:
  uv run pytest -q tests/integration

build:
  uv build

dev:
  uv run mcp dev -e . src/postgres_mcp/server.py

test:
  npx @wong2/mcp-cli uv run python -m postgres_mcp.server

nix-claude-desktop:
  NIXPKGS_ALLOW_UNFREE=1 nix run "github:k3d3/claude-desktop-linux-flake#claude-desktop-with-fhs" --impure

release-help:
  @echo "- update version in pyproject.toml"
  @echo "- uv sync"
  @echo "- git commit"
  @echo "- git push && merge to main"
  @echo '- just release 0.0.0 "note"'
  @echo 'OR'
  @echo '- just prerelease 0.0.0 1 "note"'

release version note extra="": # ="Release v{{version}}" extra="": # NOTE version format should be 0.0.0
  #!/usr/bin/env bash
  if [[ "{{version}}" == v* ]]; then
    echo "Error: Do not include 'v' prefix in version. It will be added automatically."
    exit 1
  fi
  uv build && git tag -a "v{{version}}" -m "Release v{{version}}" || true && git push --tags && gh release create "v{{version}}" --title "PostgreSQL MCP v{{version}}" --notes "{{note}}" {{extra}} dist/*.whl dist/*.tar.gz

prerelease version rc note: #="Release candidate {{rc}} for version {{version}}":
  just release "{{version}}rc{{rc}}" "{{note}}" "--prerelease"
