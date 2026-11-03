"""Tests for automated release documentation, checklist and recovery guides."""

from __future__ import annotations

from pathlib import Path


def test_checklist_no_hardcoded_version() -> None:
    root = Path(__file__).resolve().parents[2]
    checklist = (root / "docs" / "release-checklist.md").read_text(encoding="utf-8")

    assert "Release Version: `0.3.0`" not in checklist
    assert "pyproject.toml" in checklist


def test_guide_documents_uv_lock_and_tag() -> None:
    root = Path(__file__).resolve().parents[2]
    ci_cd_doc = root / "docs" / "ci-cd.md"
    assert ci_cd_doc.is_file(), "docs/ci-cd.md must exist"

    content = ci_cd_doc.read_text(encoding="utf-8")
    assert "uv lock --check" in content
    assert "vX.Y.Z" in content
    assert "ghcr.io/diaszano/postgres-mcp" in content


def test_guide_documents_partial_release_recovery() -> None:
    root = Path(__file__).resolve().parents[2]
    ci_cd_doc = (root / "docs" / "ci-cd.md").read_text(encoding="utf-8")

    assert "retry-publish" in ci_cd_doc or "validate_release_ref" in ci_cd_doc


def test_guide_has_ghcr_pull_by_digest() -> None:
    root = Path(__file__).resolve().parents[2]
    ci_cd_doc = (root / "docs" / "ci-cd.md").read_text(encoding="utf-8")

    assert "@sha256:" in ci_cd_doc
