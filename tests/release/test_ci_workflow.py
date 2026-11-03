from __future__ import annotations

from pathlib import Path

import yaml


def test_ci_triggers_pr_and_main() -> None:
    root = Path(__file__).resolve().parents[2]
    ci_path = root / ".github" / "workflows" / "ci.yml"

    assert ci_path.is_file(), ".github/workflows/ci.yml file missing"
    # Use BaseLoader to prevent YAML 1.1 'on' being parsed as boolean True
    content = yaml.load(ci_path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)

    on_events = content.get("on") or content.get(True)
    assert on_events is not None, "Workflow must define 'on' triggers"
    assert "pull_request" in on_events, "Workflow must trigger on 'pull_request'"
    assert "push" in on_events, "Workflow must trigger on 'push'"

    push_branches = on_events["push"].get("branches", [])
    assert "main" in push_branches, "Push trigger must include 'main' branch"


def test_pr_jobs_have_read_only_permissions() -> None:
    root = Path(__file__).resolve().parents[2]
    ci_path = root / ".github" / "workflows" / "ci.yml"

    assert ci_path.is_file(), ".github/workflows/ci.yml file missing"
    content = yaml.load(ci_path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)

    # Top-level permissions must be read-only
    top_permissions = content.get("permissions", {})
    assert top_permissions.get("contents") == "read", "Top-level permissions must specify 'contents: read'"
    assert top_permissions.get("packages") is None, "Top-level must not grant 'packages: write'"

    # Verify no job escalates to contents: write or packages: write during PR validation
    jobs = content.get("jobs", {})
    for job_name, job_def in jobs.items():
        if job_name in ("conventions", "lint", "typecheck", "unit", "integration"):
            job_perms = job_def.get("permissions", {})
            assert job_perms.get("contents") != "write", f"Job '{job_name}' must not have 'contents: write'"
            assert job_perms.get("packages") != "write", f"Job '{job_name}' must not have 'packages: write'"


def test_conventions_job_runs_safe_validation() -> None:
    root = Path(__file__).resolve().parents[2]
    ci_path = root / ".github" / "workflows" / "ci.yml"

    raw_text = ci_path.read_text(encoding="utf-8")
    assert "scripts/ci/check_pr_metadata.py" in raw_text, "Conventions job must call check_pr_metadata.py"

    content = yaml.load(raw_text, Loader=yaml.BaseLoader)
    conventions_job = content.get("jobs", {}).get("conventions")
    assert conventions_job is not None, "Workflow must have a 'conventions' job"

    # Verify env is used rather than unsafe shell interpolation
    raw_conventions = yaml.dump(conventions_job)
    assert "PR_TITLE:" in raw_conventions or "PR_HEAD_REF:" in raw_conventions, "Metadata must be passed via env vars"
    assert "${{ github.event.pull_request.title }}" not in raw_conventions.replace("PR_TITLE: ${{ github.event.pull_request.title }}", ""), (
        "Unsanitized PR title must not be interpolated directly in shell commands"
    )


def test_ci_revalidates_edited_pr_title() -> None:
    root = Path(__file__).resolve().parents[2]
    content = yaml.load((root / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8"), Loader=yaml.BaseLoader)

    pull_request = content["on"]["pull_request"]
    assert set(pull_request["types"]) >= {"opened", "synchronize", "reopened", "edited"}
    validation = next(step for step in content["jobs"]["conventions"]["steps"] if step.get("name") == "Validate PR metadata")
    env = validation["env"]
    assert env["PR_AUTHOR"] == "${{ github.event.pull_request.user.login }}"
    assert "GITHUB_ACTOR" not in env


def test_ci_uses_a_uv_version_that_reads_the_checked_lockfile() -> None:
    root = Path(__file__).resolve().parents[2]
    content = yaml.load((root / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8"), Loader=yaml.BaseLoader)

    workflows = [content, yaml.load((root / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8"), Loader=yaml.BaseLoader)]
    versions = {
        step["with"].get("version")
        for workflow in workflows
        for job in workflow.get("jobs", {}).values()
        for step in job.get("steps", [])
        if step.get("uses", "").startswith("astral-sh/setup-uv@")
    }
    assert versions == {"0.13.7"}
