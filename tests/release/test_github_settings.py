"""Tests for repository governance, GitHub settings and rollback documentation."""

from __future__ import annotations

from pathlib import Path


def test_settings_require_main_protection() -> None:
    root = Path(__file__).resolve().parents[2]
    settings_file = root / "docs" / "github-settings.md"
    assert settings_file.is_file(), "docs/github-settings.md missing"
    content = settings_file.read_text(encoding="utf-8").lower()

    assert "branch protection" in content or "ruleset" in content
    assert "main" in content
    assert "require status checks" in content or "status checks" in content


def test_settings_document_release_bot_push_permission() -> None:
    root = Path(__file__).resolve().parents[2]
    content = (root / "docs" / "github-settings.md").read_text(encoding="utf-8")

    assert "github_token" in content.lower() or "actions bot" in content.lower()
    assert "contents: write" in content.lower() or "bypass" in content.lower()


def test_settings_restrict_force_tag_and_fork_secrets() -> None:
    root = Path(__file__).resolve().parents[2]
    content = (root / "docs" / "github-settings.md").read_text(encoding="utf-8").lower()

    assert "force push" in content or "restrict deletions" in content
    assert "tag" in content


def test_rollback_by_digest_documented() -> None:
    root = Path(__file__).resolve().parents[2]
    content = (root / "docs" / "github-settings.md").read_text(encoding="utf-8")

    assert "sha256:" in content or "digest" in content.lower()
    assert "rollback" in content.lower()


def test_security_md_references_github_governance() -> None:
    root = Path(__file__).resolve().parents[2]
    security_md = (root / "SECURITY.md").read_text(encoding="utf-8")

    assert "github-settings.md" in security_md or "governance" in security_md.lower()
