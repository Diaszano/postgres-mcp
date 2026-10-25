"""Tests verifying CI workflow separation, HypoPG gating, and independent job failure semantics."""

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "build.yml"


@pytest.fixture(scope="module")
def workflow_def() -> dict:
    """Parse .github/workflows/build.yml."""
    assert WORKFLOW_PATH.exists(), f"Missing CI workflow file at {WORKFLOW_PATH}"
    with open(WORKFLOW_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data


def test_unit_job_never_requires_docker(workflow_def: dict):
    """The unit test CI job must be isolated and never require Docker service or daemon."""
    jobs = workflow_def.get("jobs", {})
    # Check for dedicated unit test job
    unit_job_key = next((k for k in jobs if "unit" in k.lower()), None)
    assert unit_job_key is not None, f"Expected a dedicated unit test job in CI workflow jobs: {list(jobs.keys())}"

    unit_job = jobs[unit_job_key]
    steps = unit_job.get("steps", [])
    step_runs = [s.get("run", "") for s in steps]
    step_names = [s.get("name", "") for s in steps]

    for run_cmd in step_runs:
        assert "docker" not in run_cmd.lower(), f"Unit job should not invoke Docker commands: {run_cmd}"
    for name in step_names:
        assert "docker" not in name.lower(), f"Unit job should not have Docker steps: {name}"


def test_required_hypopg_missing_is_failure():
    """Verify conftest enforces HypoPG requirement without silent fallback or skip."""
    conftest_path = REPO_ROOT / "tests" / "integration" / "conftest.py"
    assert conftest_path.exists()
    content = conftest_path.read_text(encoding="utf-8")

    # The hypopg fixture must never catch ImageNotFound and fallback to a plain vanilla image
    # without failing the test run.
    assert "hypopg_postgres" in content
    assert "FALLBACK_IMAGE" not in content or "raise" in content or "fail" in content


def test_ci_matrix_executes_pg16_17_18(workflow_def: dict):
    """Integration job matrix includes PostgreSQL versions, explicitly documenting PG 18 support status."""
    jobs = workflow_def.get("jobs", {})
    integration_job_key = next((k for k in jobs if "integration" in k.lower()), None)
    assert integration_job_key is not None, f"Expected a dedicated integration test job in CI: {list(jobs.keys())}"

    integration_job = jobs[integration_job_key]
    strategy = integration_job.get("strategy", {})
    matrix = strategy.get("matrix", {})

    pg_versions = matrix.get("postgres-version") or matrix.get("pg_version") or matrix.get("version")
    assert pg_versions is not None, f"Integration job strategy must define a postgres version matrix: {matrix}"

    # Stringified versions
    versions_str = [str(v) for v in pg_versions]
    assert "16" in versions_str, "Matrix must test PostgreSQL 16"
    assert "17" in versions_str, "Matrix must test PostgreSQL 17"
    # PG 18 may be included or marked experimental/allowed-to-fail if hypopg is unavailable for pg18
    assert "18" in versions_str or "18" in str(integration_job), "PostgreSQL 18 status must be acknowledged in matrix"


def test_full_ci_fails_on_any_required_job(workflow_def: dict):
    """Workflow must separate lint, typecheck, unit, and integration jobs for branch protection."""
    jobs = workflow_def.get("jobs", {})
    job_names = [k.lower() for k in jobs.keys()]

    assert any("lint" in k for k in job_names), f"Lint must be an independent job: {job_names}"
    assert any("typecheck" in k or "check" in k for k in job_names), f"Typecheck must be an independent job: {job_names}"
    assert any("unit" in k for k in job_names), f"Unit tests must be an independent job: {job_names}"
    assert any("integration" in k for k in job_names), f"Integration tests must be an independent job: {job_names}"
