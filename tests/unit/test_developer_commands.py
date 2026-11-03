"""Unit tests for developer workflow commands, justfile, and project lock integrity."""

import shutil
import subprocess
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_just_commands_reference_real_package():
    """Verify justfile recipes exist and target the real postgres_mcp package."""
    justfile_path = REPO_ROOT / "justfile"
    assert justfile_path.exists(), "justfile must exist in repository root"
    content = justfile_path.read_text(encoding="utf-8")

    # Obsolete names must never appear
    assert "crystaldba" not in content, "Obsolete 'crystaldba' package path must be removed from justfile"

    # Required developer recipes
    required_recipes = ["lint", "typecheck", "test-unit", "test-integration", "build"]
    for recipe in required_recipes:
        assert f"{recipe}:" in content or f"\n{recipe}" in content, f"Recipe '{recipe}' must be declared in justfile"

    # If `just` binary is available, test `just --list` execution
    if shutil.which("just"):
        res = subprocess.run(
            ["just", "--list"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        for recipe in required_recipes:
            assert recipe in res.stdout, f"'{recipe}' should be listed in `just --list`"


def test_lock_matches_pyproject():
    """Verify uv lock --check passes and locks pglast==7.11 without unreviewed bump."""
    res = subprocess.run(
        ["uv", "lock", "--check"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, f"uv lock --check failed:\nSTDOUT: {res.stdout}\nSTDERR: {res.stderr}"

    lockfile_path = REPO_ROOT / "uv.lock"
    assert lockfile_path.exists()
    lock_content = lockfile_path.read_text(encoding="utf-8")
    assert 'version = "7.11"' in lock_content, "pglast must remain pinned to 7.11 in uv.lock"


def test_python_and_ruff_consistency():
    """Verify ruff and pyright target versions align with Python >=3.12 requirement."""
    pyproject_path = REPO_ROOT / "pyproject.toml"
    assert pyproject_path.exists()
    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)

    project = data.get("project", {})
    assert project.get("requires-python") == ">=3.12"

    ruff_target = data.get("tool", {}).get("ruff", {}).get("target-version")
    assert ruff_target == "py312", f"Ruff target-version should be 'py312', got '{ruff_target}'"

    pyright_version = data.get("tool", {}).get("pyright", {}).get("pythonVersion")
    assert pyright_version == "3.12", f"Pyright pythonVersion should be '3.12', got '{pyright_version}'"
