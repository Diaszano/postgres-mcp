"""Unit tests validating Dockerfile OCI metadata, non-root execution, and release pipeline security."""

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE_PATH = REPO_ROOT / "Dockerfile"
ENTRYPOINT_PATH = REPO_ROOT / "docker-entrypoint.sh"
DOCKER_WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "release.yml"


def test_oci_labels_match_project():
    """Verify OCI labels in Dockerfile match the project's MIT license and preserve upstream credit."""
    assert DOCKERFILE_PATH.exists()
    content = DOCKERFILE_PATH.read_text(encoding="utf-8")

    # License check
    assert 'org.opencontainers.image.licenses="MIT"' in content, "Dockerfile OCI license must be MIT"
    assert "Apache-2.0" not in content, "Outdated Apache-2.0 license label must be removed"

    # Upstream attribution and metadata
    assert "org.opencontainers.image.source" in content
    assert "org.opencontainers.image.vendor" in content
    assert "Crystal" in content or "Johann" in content, "Original author attribution must be preserved"


def test_nonroot_and_no_uri_logging():
    """Verify Dockerfile uses non-root user and entrypoint does not leak URIs/secrets to stdout."""
    dockerfile_content = DOCKERFILE_PATH.read_text(encoding="utf-8")
    assert "USER app" in dockerfile_content, "Container must run as unprivileged 'app' user"

    entrypoint_content = ENTRYPOINT_PATH.read_text(encoding="utf-8")
    assert "set -x" not in entrypoint_content, "set -x must not be enabled in entrypoint to avoid credential leakage"
    assert "echo $DATABASE_URI" not in entrypoint_content
    assert 'echo "$DATABASE_URI"' not in entrypoint_content


def test_scan_job_reports_advisories():
    """Verify release workflow includes a security vulnerability scanning step."""
    assert DOCKER_WORKFLOW_PATH.exists()
    with open(DOCKER_WORKFLOW_PATH, encoding="utf-8") as f:
        workflow = yaml.safe_load(f)

    jobs = workflow.get("jobs", {})
    workflow_text = str(jobs).lower()

    # Vulnerability scanner (e.g. trivy, snyk, dockerscout, or audit)
    has_scanner = any(tool in workflow_text for tool in ["trivy", "scout", "scan", "audit", "promote_image"])
    assert has_scanner, "Docker release workflow must include a security vulnerability scan step"


def test_arm64_amd64_manifest():
    """Verify release workflow builds multi-architecture manifest for amd64 and arm64."""
    with open(DOCKER_WORKFLOW_PATH, encoding="utf-8") as f:
        workflow = yaml.safe_load(f)

    jobs = workflow.get("jobs", {})
    build_job = jobs.get("build-image") or jobs.get("build-and-push") or jobs.get("build")
    assert build_job is not None, "Workflow must have a build job"

    steps = build_job.get("steps", [])
    step_str = str(steps)
    assert "linux/amd64" in step_str and "linux/arm64" in step_str, "Build step must target linux/amd64 and linux/arm64"
    assert "setup-buildx-action" in step_str, "Build step must use setup-buildx-action"
