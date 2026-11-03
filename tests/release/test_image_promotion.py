"""Tests for GHCR image promotion script and workflow integration."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

from scripts.ci.validate_release import compare_release_versions


def _load_release_workflow() -> dict[str, Any]:
    root = Path(__file__).resolve().parents[2]
    path = root / ".github" / "workflows" / "release.yml"
    assert path.is_file(), ".github/workflows/release.yml missing"
    return yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


def test_promotion_script_syntax_and_guards() -> None:
    root = Path(__file__).resolve().parents[2]
    script_path = root / "scripts" / "ci" / "promote_image.sh"
    assert script_path.is_file(), "scripts/ci/promote_image.sh missing"
    content = script_path.read_text(encoding="utf-8")

    assert "#!/usr/bin/env bash" in content
    assert "set -euo pipefail" in content
    assert "imagetools create" in content
    assert "scan_image.sh" in content
    assert "sha256:" in content


def _fake_tools(tmp_path: Path) -> tuple[Path, Path, Path]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    docker_log = tmp_path / "docker.jsonl"
    trivy_log = tmp_path / "trivy.log"
    docker = bin_dir / "docker"
    docker.write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        "args = sys.argv[1:]\n"
        "with open(os.environ['DOCKER_LOG'], 'a') as log: log.write(json.dumps(args) + '\\n')\n"
        "manifests = json.loads(os.environ.get('MANIFESTS', '{}'))\n"
        "versions = json.loads(os.environ.get('VERSIONS', '{}'))\n"
        "if args[:3] == ['buildx', 'imagetools', 'inspect']:\n"
        "    ref = args[-1]\n"
        "    if os.environ.get('INSPECT_ERROR'):\n"
        "        print(os.environ['INSPECT_ERROR'], file=sys.stderr); sys.exit(2)\n"
        "    if '--format' in args:\n"
        "        version = versions.get(ref)\n"
        "        labels = {'org.opencontainers.image.version': version} if version else {}\n"
        "        print(json.dumps({'linux/amd64': {'config': {'Labels': labels}}}))\n"
        "    elif ref in manifests:\n"
        "        print('Digest: ' + manifests[ref])\n"
        "    else:\n"
        "        print('ERROR: manifest unknown', file=sys.stderr); sys.exit(1)\n"
        "elif args[:3] == ['buildx', 'imagetools', 'create']:\n"
        "    if os.environ.get('PROMOTE_ERROR'):\n"
        "        print('promotion failed', file=sys.stderr); sys.exit(1)\n"
        "else:\n"
        "    print('unexpected docker command: ' + repr(args), file=sys.stderr); sys.exit(2)\n",
        encoding="utf-8",
    )
    trivy = bin_dir / "trivy"
    trivy.write_text(
        "#!/bin/bash\n"
        'printf "%s\\n" "$*" >> "$TRIVY_LOG"\n'
        'if [[ -n "${TRIVY_FAIL_PLATFORM:-}" && "$*" == *"${TRIVY_FAIL_PLATFORM}"* ]]; then exit 9; fi\n',
        encoding="utf-8",
    )
    docker.chmod(0o755)
    trivy.chmod(0o755)
    return bin_dir, docker_log, trivy_log


def _run_promotion(
    tmp_path: Path,
    *,
    repository: str = "ghcr.io/diaszano/postgres-mcp",
    digest: str = "sha256:" + "a" * 64,
    tag: str = "v0.3.2",
    manifests: dict[str, str] | None = None,
    versions: dict[str, str] | None = None,
    trivy_fail_platform: str = "",
    include_trivy: bool = True,
    inspect_error: str = "",
) -> tuple[subprocess.CompletedProcess[str], list[list[str]], str]:
    root = Path(__file__).resolve().parents[2]
    bin_dir, docker_log, trivy_log = _fake_tools(tmp_path)
    if not include_trivy:
        (bin_dir / "trivy").unlink()
    env = {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "DOCKER_LOG": str(docker_log),
        "TRIVY_LOG": str(trivy_log),
        "MANIFESTS": json.dumps(manifests or {}),
        "VERSIONS": json.dumps(versions or {}),
        "TRIVY_FAIL_PLATFORM": trivy_fail_platform,
        "INSPECT_ERROR": inspect_error,
    }
    result = subprocess.run([str(root / "scripts/ci/promote_image.sh"), repository, digest, tag], cwd=root, env=env, capture_output=True, text=True)
    docker_calls = [json.loads(line) for line in docker_log.read_text(encoding="utf-8").splitlines()] if docker_log.exists() else []
    trivy_calls = trivy_log.read_text(encoding="utf-8") if trivy_log.exists() else ""
    return result, docker_calls, trivy_calls


def test_promote_image_calculates_aliases(tmp_path: Path) -> None:
    result, calls, trivy_calls = _run_promotion(tmp_path)

    assert result.returncode == 0, result.stderr
    create = next(call for call in calls if call[:3] == ["buildx", "imagetools", "create"])
    assert create == [
        "buildx",
        "imagetools",
        "create",
        "--tag",
        "ghcr.io/diaszano/postgres-mcp:v0.3.2",
        "--tag",
        "ghcr.io/diaszano/postgres-mcp:0.3.2",
        "--tag",
        "ghcr.io/diaszano/postgres-mcp:0.3",
        "--tag",
        "ghcr.io/diaszano/postgres-mcp:0",
        "--tag",
        "ghcr.io/diaszano/postgres-mcp:latest",
        "ghcr.io/diaszano/postgres-mcp@sha256:" + "a" * 64,
    ]
    assert "--platform linux/amd64" in trivy_calls
    assert "--platform linux/arm64" in trivy_calls


@pytest.mark.parametrize(
    ("repository", "digest", "tag"),
    [
        ("ghcr.io/diaszano/postgres-mcp", "sha256:bad", "v0.3.2"),
        ("ghcr.io/diaszano/postgres-mcp", "sha256:" + "a" * 64, "v0.3.2;touch /tmp/pwned"),
        ("ghcr.io/diaszano/postgres-mcp;touch /tmp/pwned", "sha256:" + "a" * 64, "v0.3.2"),
    ],
)
def test_invalid_inputs_fail_without_promotion(tmp_path: Path, repository: str, digest: str, tag: str) -> None:
    result, calls, _ = _run_promotion(tmp_path, repository=repository, digest=digest, tag=tag)

    assert result.returncode != 0
    assert not any(call[:3] == ["buildx", "imagetools", "create"] for call in calls)


def test_missing_trivy_fails_before_promotion(tmp_path: Path) -> None:
    result, calls, _ = _run_promotion(tmp_path, include_trivy=False)

    assert result.returncode != 0
    assert not any(call[:3] == ["buildx", "imagetools", "create"] for call in calls)


@pytest.mark.parametrize("platform", ["linux/amd64", "linux/arm64"])
def test_scan_failure_on_either_platform_blocks_promotion(tmp_path: Path, platform: str) -> None:
    result, calls, trivy_calls = _run_promotion(tmp_path, trivy_fail_platform=platform)

    assert result.returncode != 0
    assert platform in trivy_calls
    assert not any(call[:3] == ["buildx", "imagetools", "create"] for call in calls)


@pytest.mark.parametrize("version_tag", ["v0.3.2", "0.3.2"])
def test_existing_immutable_version_tag_cannot_change_digest(tmp_path: Path, version_tag: str) -> None:
    repository = "ghcr.io/diaszano/postgres-mcp"
    result, calls, _ = _run_promotion(tmp_path, manifests={f"{repository}:{version_tag}": "sha256:" + "b" * 64})

    assert result.returncode != 0
    assert "immutable" in result.stderr.lower()
    assert not any(call[:3] == ["buildx", "imagetools", "create"] for call in calls)


def test_unknown_manifest_state_fails_closed(tmp_path: Path) -> None:
    result, calls, _ = _run_promotion(tmp_path, inspect_error="denied: unauthorized")

    assert result.returncode != 0
    assert "inspect" in result.stderr.lower()
    assert not any(call[:3] == ["buildx", "imagetools", "create"] for call in calls)


def test_recovery_never_downgrades_newer_aliases(tmp_path: Path) -> None:
    repository = "ghcr.io/diaszano/postgres-mcp"
    newer = "sha256:" + "b" * 64
    aliases = [f"{repository}:1.2", f"{repository}:1", f"{repository}:latest"]
    manifests = {alias: newer for alias in aliases}
    versions = {alias: "1.2.4" for alias in aliases}
    result, calls, _ = _run_promotion(tmp_path, tag="v1.2.3", manifests=manifests, versions=versions)

    assert result.returncode == 0, result.stderr
    create = next(call for call in calls if call[:3] == ["buildx", "imagetools", "create"])
    assert create.count("--tag") == 2
    assert f"{repository}:v1.2.3" in create
    assert f"{repository}:1.2.3" in create
    assert all(alias not in create for alias in aliases)


def test_unreadable_alias_version_fails_without_guessing(tmp_path: Path) -> None:
    repository = "ghcr.io/diaszano/postgres-mcp"
    result, calls, _ = _run_promotion(
        tmp_path,
        tag="v1.2.3",
        manifests={f"{repository}:latest": "sha256:" + "b" * 64},
    )

    assert result.returncode != 0
    assert "version" in result.stderr.lower()
    assert not any(call[:3] == ["buildx", "imagetools", "create"] for call in calls)


def test_release_version_comparison_is_numeric() -> None:
    assert compare_release_versions("1.10.0", "1.9.99") == 1
    assert compare_release_versions("1.2.3", "1.2.3") == 0
    assert compare_release_versions("1.2.3", "1.2.4") == -1


def test_existing_alias_with_same_digest_is_idempotent(tmp_path: Path) -> None:
    repository = "ghcr.io/diaszano/postgres-mcp"
    digest = "sha256:" + "a" * 64
    tags = ["v1.2.3", "1.2.3", "1.2", "1", "latest"]
    manifests = {f"{repository}:{tag}": digest for tag in tags}
    result, calls, _ = _run_promotion(tmp_path, digest=digest, tag="v1.2.3", manifests=manifests)

    assert result.returncode == 0, result.stderr
    assert not any(call[:3] == ["buildx", "imagetools", "create"] for call in calls)


def test_release_workflow_includes_promotion_job() -> None:
    wf = _load_release_workflow()
    jobs = wf.get("jobs", {})
    assert "promote-image" in jobs, "release.yml must include 'promote-image' job"

    job = jobs["promote-image"]
    needs = job.get("needs", [])
    assert "build-image" in needs
    assert job.get("permissions", {}).get("packages") == "write"

    steps_text = yaml.dump(job.get("steps", []))
    assert "promote_image.sh" in steps_text
    checkout = next(step for step in job["steps"] if step.get("name") == "Checkout release commit")
    assert checkout["with"]["ref"] == "${{ needs.semantic-release.outputs.release_sha }}"
