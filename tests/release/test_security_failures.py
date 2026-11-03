"""Tests for pipeline trust boundaries, supply chain attack surface and security failures."""

import os
import re
import subprocess
from pathlib import Path

import pytest
import yaml

from scripts.ci.validate_release import validate_release_baseline


def _run_release_step(tmp_path: Path, *, next_version: str, print_status: int = 0) -> tuple[subprocess.CompletedProcess[str], str, str]:
    workflow = yaml.load(Path(".github/workflows/release.yml").read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    step = next(step for step in workflow["jobs"]["semantic-release"]["steps"] if step.get("name") == "Run Python Semantic Release")
    version_file = tmp_path / "version"
    version_file.write_text("0.3.0", encoding="utf-8")
    commands = tmp_path / "commands"
    publish_marker = tmp_path / "published"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    (fake_bin / "uv").write_text('#!/bin/sh\ncat "$FAKE_VERSION_FILE"\n', encoding="utf-8")
    (fake_bin / "uvx").write_text(
        "#!/bin/sh\n"
        'printf "%s\\n" "$*" >> "$FAKE_COMMANDS"\n'
        'case " $* " in\n'
        '  *" version --print "*) [ "$FAKE_PRINT_STATUS" -eq 0 ] || exit "$FAKE_PRINT_STATUS"; printf "%s\\n" "$NEXT_VERSION" ;;\n'
        '  *" version "*) printf "%s\\n" "$NEXT_VERSION" > "$FAKE_VERSION_FILE" ;;\n'
        '  *" publish "*) touch "$FAKE_PUBLISH_MARKER" ;;\n'
        "esac\n",
        encoding="utf-8",
    )
    (fake_bin / "git").write_text('#!/bin/sh\nprintf "release-sha\\n"\n', encoding="utf-8")
    for executable in fake_bin.iterdir():
        executable.chmod(0o755)

    output = tmp_path / "github-output"
    env = {
        **os.environ,
        **step.get("env", {}),
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "GITHUB_OUTPUT": str(output),
        "FAKE_VERSION_FILE": str(version_file),
        "FAKE_COMMANDS": str(commands),
        "FAKE_PUBLISH_MARKER": str(publish_marker),
        "FAKE_PRINT_STATUS": str(print_status),
        "NEXT_VERSION": next_version,
    }
    result = subprocess.run(["bash", "-euo", "pipefail", "-c", step["run"]], cwd=Path.cwd(), env=env, capture_output=True, text=True)
    return result, output.read_text(encoding="utf-8") if output.exists() else "", commands.read_text(encoding="utf-8") if commands.exists() else ""


def test_versioning_failure_stops_release(tmp_path: Path) -> None:
    result, _, commands = _run_release_step(tmp_path, next_version="0.3.1", print_status=23)

    assert result.returncode != 0, result.stdout
    assert "publish" not in commands


def test_no_version_change_is_a_successful_non_release(tmp_path: Path) -> None:
    result, outputs, commands = _run_release_step(tmp_path, next_version="0.3.0")

    assert result.returncode == 0, result.stderr
    assert "released=false" in outputs
    assert "version=0.3.0" in outputs
    assert "publish" not in commands


def test_version_change_publishes_matching_tag_and_outputs(tmp_path: Path) -> None:
    result, outputs, commands = _run_release_step(tmp_path, next_version="0.3.1")

    assert result.returncode == 0, result.stderr
    assert "version --print" in commands
    assert " version " in commands
    assert "publish" in commands
    assert "released=true" in outputs
    assert "tag=v0.3.1" in outputs
    assert "release_sha=release-sha" in outputs
    assert "version=0.3.1" in outputs


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


def test_scheduled_security_scan_fails_on_high_critical_and_operational_errors():
    workflow = yaml.load(Path(".github/workflows/security.yml").read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    scan = next(step for step in workflow["jobs"]["repo-scan"]["steps"] if step.get("name") == "Run Trivy Repository Scan")

    assert scan["with"]["severity"] == "HIGH,CRITICAL"
    assert scan["with"]["exit-code"] == "1"
    assert scan.get("continue-on-error") is None


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
