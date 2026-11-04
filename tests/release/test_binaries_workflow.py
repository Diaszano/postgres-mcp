"""Tests for GitHub Actions standalone binary release workflow."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def _load_workflow() -> dict[str, Any]:
    root = Path(__file__).resolve().parents[2]
    workflow_path = root / ".github" / "workflows" / "binaries.yml"
    assert workflow_path.is_file(), ".github/workflows/binaries.yml missing"
    return yaml.load(workflow_path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


def test_binaries_workflow_triggers() -> None:
    wf = _load_workflow()
    triggers = wf.get("on", {})
    assert "release" in triggers or "workflow_dispatch" in triggers
    if "release" in triggers:
        assert triggers["release"].get("types") == ["published"]


def test_binaries_workflow_matrix_platforms() -> None:
    wf = _load_workflow()
    build_job = wf.get("jobs", {}).get("build-binaries", {})
    assert build_job, "jobs.build-binaries must exist"

    strategy = build_job.get("strategy", {})
    matrix = strategy.get("matrix", {})
    include = matrix.get("include", [])
    assert include, "matrix.include must specify target configurations"

    combos = {(item["target_os"], item["target_arch"], item["runner"]) for item in include}
    assert ("darwin", "arm64", "macos-latest") in combos
    assert ("darwin", "amd64", "macos-13") in combos
    assert ("linux", "amd64", "ubuntu-latest") in combos
    assert ("linux", "arm64", "ubuntu-24.04-arm") in combos


def test_binaries_workflow_calls_build_script_and_uploads() -> None:
    wf = _load_workflow()
    build_job = wf.get("jobs", {}).get("build-binaries", {})
    steps = build_job.get("steps", [])
    steps_text = yaml.dump(steps)

    assert "build_binary.sh" in steps_text
    assert "gh release upload" in steps_text or "upload-release-asset" in steps_text or "action-gh-release" in steps_text
