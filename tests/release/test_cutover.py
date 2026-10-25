"""Tests for complete CI/CD cutover from legacy workflows to GHCR semantic releases."""

from __future__ import annotations

from pathlib import Path

import yaml


def test_legacy_workflows_completely_removed() -> None:
    root = Path(__file__).resolve().parents[2]
    workflows_dir = root / ".github" / "workflows"

    legacy_files = [
        "build.yml",
        "build.yml.disabled",
        "docker-build-dockerhub.yml",
        "docker-build-dockerhub.yml.disabled",
    ]
    for fname in legacy_files:
        assert not (workflows_dir / fname).exists(), f"Legacy workflow {fname} must be removed from repository"


def test_only_one_main_release_entry() -> None:
    root = Path(__file__).resolve().parents[2]
    workflows_dir = root / ".github" / "workflows"

    # Search for any active workflow that runs on push to main with release logic
    release_callers = []
    for wf_path in workflows_dir.glob("*.yml"):
        content = yaml.load(wf_path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
        on_events = content.get("on") or content.get(True) or {}
        if "push" in on_events:
            push_config = on_events.get("push", {})
            branches = push_config.get("branches", [])
            if "main" in branches:
                jobs = content.get("jobs", {})
                if "release" in jobs:
                    release_callers.append(wf_path.name)

    assert release_callers == ["ci.yml"], f"Only ci.yml must trigger releases on main, found: {release_callers}"


def test_no_dockerhub_references_in_active_workflows() -> None:
    root = Path(__file__).resolve().parents[2]
    workflows_dir = root / ".github" / "workflows"

    for wf_path in workflows_dir.glob("*.yml"):
        content = wf_path.read_text(encoding="utf-8")
        assert "docker.io" not in content.lower(), f"{wf_path.name} contains reference to docker.io"
        assert "dockerhub" not in content.lower(), f"{wf_path.name} contains reference to dockerhub"


def test_ghcr_primary_image_reference() -> None:
    root = Path(__file__).resolve().parents[2]
    release_wf = root / ".github" / "workflows" / "release.yml"
    assert release_wf.is_file()
    content = release_wf.read_text(encoding="utf-8")

    assert "ghcr.io/diaszano/postgres-mcp" in content


def test_release_checklist_documents_ghcr_and_psr() -> None:
    root = Path(__file__).resolve().parents[2]
    checklist = (root / "docs" / "release-checklist.md").read_text(encoding="utf-8")

    assert "GHCR" in checklist
    assert "Semantic Release" in checklist or "PSR" in checklist
    assert "ghcr.io/diaszano/postgres-mcp" in checklist
