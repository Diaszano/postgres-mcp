"""Tests for GHCR multiarch image staging, Dockerfile OCI labels and manifest integrity."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def _load_release_workflow() -> dict[str, Any]:
    root = Path(__file__).resolve().parents[2]
    path = root / ".github" / "workflows" / "release.yml"
    assert path.is_file(), ".github/workflows/release.yml missing"
    return yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


def test_build_image_job_structure() -> None:
    wf = _load_release_workflow()
    jobs = wf.get("jobs", {})
    assert "build-image" in jobs, "release.yml must define a 'build-image' job"

    job = jobs["build-image"]
    needs = job.get("needs")
    assert needs == "semantic-release" or "semantic-release" in needs
    assert job.get("permissions", {}).get("packages") == "write"

    condition = job.get("if", "")
    assert "needs.semantic-release.outputs.released == 'true'" in condition


def test_image_platforms_and_registry() -> None:
    wf = _load_release_workflow()
    job = wf.get("jobs", {}).get("build-image", {})
    steps = job.get("steps", [])
    build_step = next((s for s in steps if "build-push-action" in s.get("uses", "")), None)
    assert build_step is not None, "Missing build-push-action step"

    with_config = build_step.get("with", {})
    assert "linux/amd64,linux/arm64" in with_config.get("platforms", "")
    assert "ghcr.io/diaszano/pgscope" in with_config.get("tags", "")


def test_staging_tag_uses_full_sha_and_attestations() -> None:
    wf = _load_release_workflow()
    job = wf.get("jobs", {}).get("build-image", {})
    steps = job.get("steps", [])
    build_step = next((s for s in steps if "build-push-action" in s.get("uses", "")), None)
    assert build_step is not None

    with_config = build_step.get("with", {})
    assert "sha-${{ needs.semantic-release.outputs.release_sha }}" in with_config.get("tags", "")
    assert with_config.get("provenance") in ("true", True)
    assert with_config.get("sbom") in ("true", True)


def test_dockerfile_oci_labels() -> None:
    root = Path(__file__).resolve().parents[2]
    dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")

    assert "https://github.com/diaszano/pgscope" in dockerfile
    assert "org.opencontainers.image.source" in dockerfile
    assert "org.opencontainers.image.revision" in dockerfile
    assert 'org.opencontainers.image.version="${VERSION}"' in dockerfile


def test_image_builds_stamp_the_release_version() -> None:
    for workflow_name, job_name, expression in [
        ("release.yml", "build-image", "${{ needs.semantic-release.outputs.version }}"),
        ("retry-publish.yml", "republish-image", "${{ needs.validate-ref.outputs.version }}"),
    ]:
        root = Path(__file__).resolve().parents[2]
        workflow = yaml.load((root / ".github" / "workflows" / workflow_name).read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
        build = next(step for step in workflow["jobs"][job_name]["steps"] if "build-push-action" in step.get("uses", ""))
        assert f"VERSION={expression}" in build["with"]["build-args"]
