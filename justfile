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

release-smoke:
  uv run pytest -q tests/release/test_smoke.py

dev:
  uv run mcp dev -e . src/postgres_mcp/server.py

test:
  npx @wong2/mcp-cli uv run python -m postgres_mcp.server

nix-claude-desktop:
  NIXPKGS_ALLOW_UNFREE=1 nix run "github:k3d3/claude-desktop-linux-flake#claude-desktop-with-fhs" --impure

release-preview:
  uv tool run --from python-semantic-release==10.7.0 semantic-release version --print --noop
