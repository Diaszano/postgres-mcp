from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from scripts.ci.check_pr_metadata import validate_pr


@pytest.mark.parametrize(
    "title,head_ref,actor",
    [
        ("feat(api)!: add policy", "feature/policy", "Diaszano"),
        ("feat: add new feature", "feature/new-feature", "Diaszano"),
        ("fix(db): correct ttl timeout", "bugfix/fix-ttl", "Diaszano"),
        ("fix: correct query parser crash", "hotfix/parser-fix", "Diaszano"),
        ("docs: update release notes", "docs/release-notes", "Diaszano"),
        ("chore(deps): bump ruff from 0.14.0 to 0.14.13", "dependabot/pip/ruff-0.14.13", "dependabot[bot]"),
        ("refactor!: redesign engine architecture", "refactor/engine", "Diaszano"),
    ],
)
def test_validate_pr_accepts_valid_metadata(title: str, head_ref: str, actor: str) -> None:
    errors = validate_pr(title=title, head_ref=head_ref, actor=actor)
    assert errors == [], f"Expected no errors for valid PR metadata: {errors}"


@pytest.mark.parametrize(
    "title,head_ref,actor,expected_substr",
    [
        ("update stuff", "feature/valid-name", "Diaszano", "title does not match Conventional Commits"),
        ("feat: add feature", "invalid_branch_name", "Diaszano", "branch name does not match conventional branch pattern"),
        ("chore(deps): bump foo", "dependabot/uv/foo-1.0", "malicious_user", "only dependabot bot is allowed to push"),
        ("feat(): missing scope value", "feature/foo", "Diaszano", "title does not match Conventional Commits"),
        ("", "feature/foo", "Diaszano", "PR title cannot be empty"),
        ("feat: valid title", "", "Diaszano", "PR head branch cannot be empty"),
    ],
)
def test_validate_pr_rejects_invalid_metadata(title: str, head_ref: str, actor: str, expected_substr: str) -> None:
    errors = validate_pr(title=title, head_ref=head_ref, actor=actor)
    assert any(expected_substr.lower() in err.lower() for err in errors), f"Expected '{expected_substr}' in errors: {errors}"


def test_cli_execution_with_flags(tmp_path: Path) -> None:
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "ci" / "check_pr_metadata.py"

    res_ok = subprocess.run(
        [sys.executable, str(script_path), "--title", "feat: add feature", "--head-ref", "feature/feature-a", "--actor", "Diaszano"],
        capture_output=True,
        text=True,
    )
    assert res_ok.returncode == 0, res_ok.stderr

    res_fail = subprocess.run(
        [sys.executable, str(script_path), "--title", "bad title", "--head-ref", "feature/feature-a", "--actor", "Diaszano"],
        capture_output=True,
        text=True,
    )
    assert res_fail.returncode != 0
    assert "Conventional Commits" in res_fail.stderr or "Conventional Commits" in res_fail.stdout


def test_pr_and_issue_templates_exist() -> None:
    root = Path(__file__).resolve().parents[2]
    pr_template = root / ".github" / "PULL_REQUEST_TEMPLATE.md"
    bug_template = root / ".github" / "ISSUE_TEMPLATE" / "bug_report.yml"
    feat_template = root / ".github" / "ISSUE_TEMPLATE" / "feature_request.yml"

    assert pr_template.is_file(), "PULL_REQUEST_TEMPLATE.md missing"
    assert bug_template.is_file(), "bug_report.yml missing"
    assert feat_template.is_file(), "feature_request.yml missing"

    pr_content = pr_template.read_text(encoding="utf-8")
    assert "Conventional Commit" in pr_content or "conventional commits" in pr_content.lower()
