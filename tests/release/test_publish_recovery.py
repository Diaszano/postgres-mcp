"""Tests for publish-only recovery workflow and release reference validation."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from scripts.ci.validate_release_ref import validate_release_ref


def test_validate_release_ref_valid(tmp_path: Path) -> None:
    # Setup mock git repo with valid tag matching pyproject.toml
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nname = "postgres-mcp"\nversion = "0.3.0"\n', encoding="utf-8")

    # Should succeed without error
    res = validate_release_ref(tag="v0.3.0", repo_root=tmp_path)
    assert res["version"] == "0.3.0"
    assert res["tag"] == "v0.3.0"


def test_validate_release_ref_mismatch(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nname = "postgres-mcp"\nversion = "0.3.0"\n', encoding="utf-8")

    with pytest.raises(ValueError, match="does not match project version"):
        validate_release_ref(tag="v0.3.1", repo_root=tmp_path)


def test_validate_release_ref_invalid_tag_format(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nname = "postgres-mcp"\nversion = "0.3.0"\n', encoding="utf-8")

    for bad_tag in ["0.3.0", "v0.3.0-rc1", "v0.3.0; rm -rf", "latest"]:
        with pytest.raises(ValueError):
            validate_release_ref(tag=bad_tag, repo_root=tmp_path)


def test_retry_workflow_is_manual_only() -> None:
    root = Path(__file__).resolve().parents[2]
    retry_wf = root / ".github" / "workflows" / "retry-publish.yml"
    assert retry_wf.is_file(), ".github/workflows/retry-publish.yml missing"
    raw_content = retry_wf.read_text(encoding="utf-8")
    wf = yaml.load(raw_content, Loader=yaml.BaseLoader)

    on_events = wf.get("on") or wf.get(True)
    assert "workflow_dispatch" in on_events
    assert "pull_request" not in on_events
    assert "push" not in on_events
    assert "semantic-release version" not in raw_content
