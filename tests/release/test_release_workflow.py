"""Tests for the reusable semantic release workflow specification and safety invariants."""

from __future__ import annotations

from pathlib import Path

import yaml


def _load_release_workflow() -> dict:
    root = Path(__file__).resolve().parents[2]
    path = root / ".github" / "workflows" / "release.yml"
    assert path.is_file(), ".github/workflows/release.yml missing"
    return yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


def test_release_workflow_structure_and_concurrency() -> None:
    wf = _load_release_workflow()

    on_events = wf.get("on") or wf.get(True)
    assert "workflow_call" in on_events

    # Must serialize releases to avoid race conditions on tags and versions
    concurrency = wf.get("concurrency")
    assert concurrency is not None, "release.yml must define concurrency group"
    if isinstance(concurrency, dict):
        assert "release" in concurrency.get("group", "")
        assert concurrency.get("cancel-in-progress") in ("false", False)


def test_workflow_uses_uv_and_pinned_psr() -> None:
    wf = _load_release_workflow()
    jobs = wf.get("jobs", {})
    assert "semantic-release" in jobs, "release.yml must have a 'semantic-release' job"

    psr_job = jobs["semantic-release"]
    # Check permissions
    perms = psr_job.get("permissions", {})
    assert perms.get("contents") == "write"

    steps_text = yaml.dump(psr_job.get("steps", []))
    assert "astral-sh/setup-uv" in steps_text
    assert "python-semantic-release==10.7.0" in steps_text or "semantic-release" in steps_text


def test_release_job_outputs_contract() -> None:
    wf = _load_release_workflow()
    on_events = wf.get("on") or wf.get(True)
    call_config = on_events.get("workflow_call", {})
    outputs = call_config.get("outputs", {})

    expected_outputs = {"released", "tag", "release_sha", "version"}
    assert expected_outputs <= set(outputs.keys()), f"Missing required outputs: {expected_outputs - set(outputs.keys())}"


def test_release_checkout_full_depth() -> None:
    wf = _load_release_workflow()
    jobs = wf.get("jobs", {})
    psr_job = jobs.get("semantic-release", {})
    steps_text = yaml.dump(psr_job.get("steps", []))
    assert "fetch-depth: 0" in steps_text or "fetch-depth: '0'" in steps_text
