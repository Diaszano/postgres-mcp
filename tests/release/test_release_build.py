from __future__ import annotations

import os
import tomllib
from pathlib import Path


def test_build_script_structure() -> None:
    root = Path(__file__).resolve().parents[2]
    script_path = root / "scripts" / "release" / "build.sh"

    assert script_path.is_file(), "scripts/release/build.sh missing"
    assert os.access(script_path, os.X_OK), "scripts/release/build.sh must be executable"

    content = script_path.read_text(encoding="utf-8")
    assert "set -euo pipefail" in content, "Script must use strict error handling"
    assert 'uv lock --upgrade-package "$PACKAGE_NAME"' in content or "uv lock --upgrade-package" in content, (
        "Script must refresh lockfile for the root package"
    )
    assert "git add uv.lock" in content, "Script must stage updated uv.lock"
    assert "uv lock --check" in content, "Script must verify lockfile consistency"
    assert "uv build" in content, "Script must invoke uv build"


def test_pyproject_configures_build_command() -> None:
    root = Path(__file__).resolve().parents[2]
    pyproject_path = root / "pyproject.toml"

    with pyproject_path.open("rb") as f:
        data = tomllib.load(f)

    cfg = data.get("tool", {}).get("semantic_release", {})
    build_cmd = cfg.get("build_command", "")
    assert "bash scripts/release/build.sh" in build_cmd or "scripts/release/build.sh" in build_cmd, (
        f"Semantic release must configure build_command to use build.sh, got: '{build_cmd}'"
    )
