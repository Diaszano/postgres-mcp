"""End-to-end smoke tests for CI/CD, supply chain security, and GHCR delivery contracts."""

from __future__ import annotations

import os
import tomllib
from pathlib import Path


def test_cd_smoke_all_workflows_and_docs_exist() -> None:
    root = Path(__file__).resolve().parents[2]
    workflows_dir = root / ".github" / "workflows"

    # Active expected workflows
    expected_workflows = ["ci.yml", "release.yml", "retry-publish.yml", "security.yml"]
    for wf in expected_workflows:
        assert (workflows_dir / wf).is_file(), f"Expected workflow {wf} is missing"

    # Deprecated workflows must not exist
    for legacy in ["build.yml", "build.yml.disabled", "docker-build-dockerhub.yml", "docker-build-dockerhub.yml.disabled"]:
        assert not (workflows_dir / legacy).exists(), f"Legacy workflow {legacy} still exists"

    # Required documentation
    expected_docs = [
        "docs/ci-cd.md",
        "docs/release-checklist.md",
        "docs/github-settings.md",
        "docs/security-deployment.md",
        "SECURITY.md",
        "NOTICE.md",
        "CONTRIBUTING.md",
    ]
    for doc in expected_docs:
        assert (root / doc).is_file(), f"Expected documentation file {doc} is missing"


def test_cd_smoke_package_and_lock_invariants() -> None:
    root = Path(__file__).resolve().parents[2]
    pyproject_path = root / "pyproject.toml"
    assert pyproject_path.is_file()

    data = tomllib.loads(pyproject_path.read_bytes().decode("utf-8"))
    version = data.get("project", {}).get("version", "")
    assert version.count(".") == 2, f"Project version must be valid SemVer X.Y.Z, got: {version}"
    assert not version.startswith("v"), f"pyproject.toml version must be unprefixed, got: {version}"

    # Verify PSR config in pyproject.toml
    psr = data.get("tool", {}).get("semantic_release", {})
    assert psr.get("version_toml") == ["pyproject.toml:project.version"]
    assert psr.get("tag_format") == "v{version}"
    assert psr.get("major_on_zero") is False
    assert psr.get("allow_zero_version") is True


def test_cd_smoke_scripts_are_executable() -> None:
    root = Path(__file__).resolve().parents[2]
    scripts = [
        "scripts/ci/check_pr_metadata.py",
        "scripts/ci/check_version.py",
        "scripts/ci/validate_release.py",
        "scripts/ci/scan_image.sh",
        "scripts/ci/promote_image.sh",
        "scripts/ci/validate_release_ref.py",
        "scripts/ci/build_hypopg_image.sh",
        "scripts/release/build.sh",
    ]
    for s in scripts:
        path = root / s
        assert path.is_file(), f"Script {s} is missing"
        assert os.access(path, os.X_OK), f"Script {s} must be executable (+x)"


def test_cd_smoke_no_dockerhub_or_pypi_in_active_release_path() -> None:
    root = Path(__file__).resolve().parents[2]
    workflows_dir = root / ".github" / "workflows"

    for wf_path in workflows_dir.glob("*.yml"):
        content = wf_path.read_text(encoding="utf-8")
        assert "pypi" not in content.lower(), f"PyPI references prohibited in {wf_path.name}"
        assert "dockerhub" not in content.lower(), f"DockerHub references prohibited in {wf_path.name}"


def test_cd_smoke_documentation_verification_section() -> None:
    root = Path(__file__).resolve().parents[2]
    ci_cd_doc = (root / "docs" / "ci-cd.md").read_text(encoding="utf-8")

    assert "## 5. End-to-End Delivery Verification & Handoff" in ci_cd_doc
