from __future__ import annotations

from pathlib import Path

import yaml


def test_release_caller_requires_main_and_all_gates() -> None:
    root = Path(__file__).resolve().parents[2]
    ci_path = root / ".github" / "workflows" / "ci.yml"

    assert ci_path.is_file(), ".github/workflows/ci.yml missing"
    content = yaml.load(ci_path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)

    jobs = content.get("jobs", {})
    assert "release" in jobs, "CI workflow must define a gated 'release' job"

    release_job = jobs["release"]
    needs = set(release_job.get("needs", []))
    expected_gates = {"conventions", "lint", "typecheck", "unit", "package", "integration"}
    assert expected_gates <= needs, f"Release job must depend on all quality gates. Missing: {expected_gates - needs}"

    # Verify guarded condition
    condition = release_job.get("if", "")
    assert "refs/heads/main" in condition, "Release job must be restricted to refs/heads/main"
    assert "push" in condition, "Release job must only run on push events (never on pull_request)"

    # Verify reusable workflow reference
    uses = release_job.get("uses", "")
    assert uses == "./.github/workflows/release.yml" or "release.yml" in uses, f"Release job must invoke release.yml reusable workflow, got: {uses}"


def test_release_workflow_is_reusable_only() -> None:
    root = Path(__file__).resolve().parents[2]
    release_path = root / ".github" / "workflows" / "release.yml"

    assert release_path.is_file(), ".github/workflows/release.yml stub missing"
    content = yaml.load(release_path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)

    on_events = content.get("on") or content.get(True)
    assert on_events is not None, "release.yml must define 'on'"
    assert "workflow_call" in on_events, "release.yml must support 'workflow_call'"
    assert "push" not in on_events, "release.yml must not allow independent 'push' triggers"
    assert "pull_request" not in on_events, "release.yml must not allow 'pull_request' triggers"
