"""Tests for standalone binary build script syntax, flags, and structure."""

from __future__ import annotations

from pathlib import Path


def test_build_binary_script_structure_and_guards() -> None:
    root = Path(__file__).resolve().parents[2]
    script = root / "scripts" / "release" / "build_binary.sh"
    assert script.is_file(), "scripts/release/build_binary.sh must exist"

    content = script.read_text(encoding="utf-8")
    assert "#!/usr/bin/env bash" in content
    assert "set -euo pipefail" in content
    assert "pyinstaller" in content
    assert "--onefile" in content
    assert "postgres_mcp" in content
    assert "psycopg" in content
    assert "pglast" in content
    assert ".tar.gz" in content
    assert "sha256" in content


def test_main_entrypoint_exists_and_callable() -> None:
    root = Path(__file__).resolve().parents[2]
    main_file = root / "src" / "postgres_mcp" / "__main__.py"
    assert main_file.is_file(), "src/postgres_mcp/__main__.py must exist"

    content = main_file.read_text(encoding="utf-8")
    assert "from postgres_mcp import main" in content
    assert 'if __name__ == "__main__":' in content
    assert "main()" in content
