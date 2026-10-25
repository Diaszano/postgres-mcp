from __future__ import annotations

import re
from pathlib import Path

import yaml

HEX_40_REGEX = re.compile(r"@[0-9a-f]{40}$")


def test_actions_are_pinned_to_full_sha() -> None:
    root = Path(__file__).resolve().parents[2]
    workflow_dir = root / ".github" / "workflows"

    assert workflow_dir.is_dir(), ".github/workflows directory missing"

    for yml_file in workflow_dir.glob("*.yml"):
        raw_text = yml_file.read_text(encoding="utf-8")
        assert "pull_request_target" not in raw_text, f"Dangerous 'pull_request_target' trigger detected in {yml_file.name}"

        # Extract uses: directives
        for match in re.finditer(r"uses:\s+([^\s]+)", raw_text):
            action_ref = match.group(1).strip()
            # Local workflow calls or local actions (starting with ./) are allowed
            if action_ref.startswith("./"):
                continue

            assert HEX_40_REGEX.search(action_ref), f"Action '{action_ref}' in {yml_file.name} is not pinned to a full 40-character commit SHA"


def test_no_privileged_permissions_in_pr_workflow() -> None:
    root = Path(__file__).resolve().parents[2]
    ci_path = root / ".github" / "workflows" / "ci.yml"

    content = yaml.load(ci_path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    assert content.get("permissions", {}).get("contents") == "read"

    jobs = content.get("jobs", {})
    for job_name, job_def in jobs.items():
        if job_name != "release":
            perms = job_def.get("permissions", {})
            assert perms.get("contents") != "write", f"Job '{job_name}' has write permissions"
            assert perms.get("packages") != "write", f"Job '{job_name}' has packages: write"
