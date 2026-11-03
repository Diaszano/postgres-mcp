from __future__ import annotations

import os
from pathlib import Path

import yaml


def test_build_hypopg_script_structure() -> None:
    root = Path(__file__).resolve().parents[2]
    script_path = root / "scripts" / "ci" / "build_hypopg_image.sh"

    assert script_path.is_file(), "scripts/ci/build_hypopg_image.sh missing"
    assert os.access(script_path, os.X_OK), "build_hypopg_image.sh must be executable"

    content = script_path.read_text(encoding="utf-8")
    assert "set -euo pipefail" in content, "Script must use strict error handling: set -euo pipefail"
    assert "|| true" not in content, "Script must not swallow package installation failures with '|| true'"
    assert "hypopg" in content.lower(), "Script must install HypoPG extension"
    assert "docker build" in content, "Script must execute docker build"


def test_integration_matrix_in_ci() -> None:
    root = Path(__file__).resolve().parents[2]
    ci_path = root / ".github" / "workflows" / "ci.yml"

    assert ci_path.is_file(), ".github/workflows/ci.yml missing"
    content = yaml.load(ci_path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)

    jobs = content.get("jobs", {})
    assert "integration" in jobs, "CI workflow must define an 'integration' job"

    integration_job = jobs["integration"]
    strategy = integration_job.get("strategy", {})
    matrix = strategy.get("matrix", {})
    pg_versions = matrix.get("postgres-version") or matrix.get("pg_version") or []

    assert "16" in pg_versions, "Integration matrix must include PostgreSQL 16"
    assert "17" in pg_versions, "Integration matrix must include PostgreSQL 17"

    # Verify script is invoked
    raw_job = yaml.dump(integration_job)
    assert "build_hypopg_image.sh" in raw_job, "Integration job must invoke build_hypopg_image.sh"
    assert "pytest tests/integration" in raw_job or "pytest -q tests/integration" in raw_job, "Integration job must execute integration test suite"
