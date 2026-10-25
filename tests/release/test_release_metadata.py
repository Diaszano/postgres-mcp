from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from scripts.ci.check_version import check_package_version


def test_ci_has_required_quality_gates() -> None:
    root = Path(__file__).resolve().parents[2]
    ci_path = root / ".github" / "workflows" / "ci.yml"

    assert ci_path.is_file(), ".github/workflows/ci.yml missing"
    raw_ci = ci_path.read_text(encoding="utf-8")

    assert "uv lock --check" in raw_ci, "Workflow must enforce lockfile consistency with 'uv lock --check'"
    assert "uv build" in raw_ci, "Workflow must build package artifact with 'uv build'"
    assert "ruff check" in raw_ci, "Workflow must run Ruff linting"
    assert "ruff format --check" in raw_ci or "ruff format" in raw_ci, "Workflow must run Ruff format check"
    assert "pyright" in raw_ci, "Workflow must run Pyright type checking"

    content = yaml.load(raw_ci, Loader=yaml.BaseLoader)
    jobs = content.get("jobs", {})
    required_gates = {"lint", "typecheck", "unit", "package"}
    assert required_gates <= set(jobs.keys()), f"Workflow missing required gate jobs: {required_gates - set(jobs.keys())}"


def test_package_version_matching() -> None:
    root = Path(__file__).resolve().parents[2]

    # Matching tags
    assert check_package_version(tag="v0.3.0", project_dir=root) == "0.3.0"
    assert check_package_version(tag="0.3.0", project_dir=root) == "0.3.0"
    assert check_package_version(tag=None, project_dir=root) == "0.3.0"

    # Mismatched tags
    with pytest.raises(ValueError, match="Version mismatch"):
        check_package_version(tag="v1.0.0", project_dir=root)

    with pytest.raises(ValueError, match="Invalid semantic version"):
        check_package_version(tag="invalid-version", project_dir=root)


def test_check_version_cli() -> None:
    root = Path(__file__).resolve().parents[2]
    script_path = root / "scripts" / "ci" / "check_version.py"

    res_ok = subprocess.run(
        [sys.executable, str(script_path), "--tag", "v0.3.0", "--project-dir", str(root)],
        capture_output=True,
        text=True,
    )
    assert res_ok.returncode == 0, res_ok.stderr
    assert "0.3.0" in res_ok.stdout

    res_fail = subprocess.run(
        [sys.executable, str(script_path), "--tag", "v9.9.9", "--project-dir", str(root)],
        capture_output=True,
        text=True,
    )
    assert res_fail.returncode != 0
    assert "Version mismatch" in res_fail.stderr or "mismatch" in res_fail.stderr.lower()
