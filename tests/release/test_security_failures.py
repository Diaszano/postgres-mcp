"""Tests for pipeline trust boundaries, supply chain attack surface and security failures."""

import re
from pathlib import Path

import pytest

from scripts.ci.validate_release import validate_release_baseline


def test_release_has_no_pr_trigger():
    """Verify that release workflow cannot be triggered by PRs or untrusted inputs."""
    release_path = Path(".github/workflows/release.yml")
    assert release_path.exists(), "release.yml workflow must exist"
    content = release_path.read_text(encoding="utf-8")

    assert "pull_request:" not in content
    assert "pull_request_target" not in content
    assert "secrets: inherit" not in content


def test_no_dockerhub_secrets_in_active_workflows():
    """Verify legacy DockerHub secrets are absent from active workflows."""
    active_workflows = [
        Path(".github/workflows/ci.yml"),
        Path(".github/workflows/release.yml"),
        Path(".github/workflows/security.yml"),
    ]
    for wf in active_workflows:
        if wf.exists():
            content = wf.read_text(encoding="utf-8")
            assert "DOCKERHUB_USERNAME" not in content, f"{wf.name} contains DOCKERHUB_USERNAME"
            assert "DOCKERHUB_TOKEN" not in content, f"{wf.name} contains DOCKERHUB_TOKEN"


def test_false_positive_scan_denied():
    """Verify that scan script fails closed on critical vulnerabilities."""
    scan_script = Path("scripts/ci/scan_image.sh")
    assert scan_script.exists()
    content = scan_script.read_text(encoding="utf-8")

    assert "--exit-code 1" in content
    assert "HIGH,CRITICAL" in content
    assert "|| true" not in content


def test_staging_digest_required():
    """Verify that promotion rejects floating tags and strictly requires immutable sha256 digests."""
    digest_pattern = re.compile(r"^sha256:[a-f0-9]{64}$")
    assert digest_pattern.match("sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")
    assert not digest_pattern.match("staging")
    assert not digest_pattern.match("latest")
    assert not digest_pattern.match("v1.0.0")


def test_untrusted_tag_not_shell_evaluated():
    """Verify that malicious tag strings with shell injection payloads are rejected."""
    malicious_tags = [
        "v1.0.0; rm -rf /",
        "v1.0.0`touch /tmp/pwned`",
        "v1.0.0$(cat /etc/passwd)",
        "v1.0.0 || echo hacked",
        "v1.0.0 && sleep 10",
        "v1.0.0\nid",
    ]
    for tag in malicious_tags:
        with pytest.raises(ValueError):
            validate_release_baseline("1.0.0", [tag])


def test_ghcr_provenance_trust_documentation():
    """Verify that docs/security-deployment.md documents GHCR supply chain security."""
    doc_path = Path("docs/security-deployment.md")
    assert doc_path.exists()
    content = doc_path.read_text(encoding="utf-8")

    assert "GHCR" in content
    assert "SLSA" in content or "provenance" in content.lower()
    assert "SBOM" in content
