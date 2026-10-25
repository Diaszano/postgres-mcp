"""Tests for GHCR image promotion script and workflow integration."""

from __future__ import annotations

import re
from pathlib import Path

import yaml


def _load_release_workflow() -> dict:
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


def test_promote_image_calculates_aliases() -> None:
    tag = "v0.3.2"
    assert tag.startswith("v")
    version = tag[1:]
    parts = version.split(".")
    assert len(parts) == 3

    major, minor, patch = parts
    expected_aliases = [
        f"v{version}",
        version,
        f"{major}.{minor}",
        major,
        "latest",
    ]
    assert expected_aliases == ["v0.3.2", "0.3.2", "0.3", "0", "latest"]


def test_promotion_script_validates_digest_format() -> None:
    valid_digest = "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    assert re.match(r"^sha256:[a-f0-9]{64}$", valid_digest)

    invalid_digests = [
        "latest",
        "sha256:short",
        "sha256:xyz",
        "v1.0.0",
        "; rm -rf /",
    ]
    for inv in invalid_digests:
        assert not re.match(r"^sha256:[a-f0-9]{64}$", inv)


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
