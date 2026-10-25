from __future__ import annotations

from pathlib import Path


def test_codeowners_protects_critical_paths() -> None:
    root = Path(__file__).resolve().parents[2]
    codeowners_path = root / ".github" / "CODEOWNERS"

    assert codeowners_path.is_file(), ".github/CODEOWNERS file does not exist"
    content = codeowners_path.read_text(encoding="utf-8")

    assert "@Diaszano" in content, "Expected @Diaszano to be defined as maintainer/owner in CODEOWNERS"
    assert ".github/workflows/" in content, ".github/workflows/ must have owner assignment"
    assert "scripts/ci/" in content, "scripts/ci/ must have owner assignment"
    assert "pyproject.toml" in content, "pyproject.toml must have owner assignment"


def test_upstream_credit_preserved() -> None:
    root = Path(__file__).resolve().parents[2]
    license_path = root / "LICENSE"
    notice_path = root / "NOTICE.md"

    assert license_path.is_file(), "LICENSE file missing"
    license_content = license_path.read_text(encoding="utf-8")
    assert "Crystal Corp." in license_content, "Original MIT copyright to Crystal Corp. must be preserved"

    assert notice_path.is_file(), "NOTICE.md file missing"
    notice_content = notice_path.read_text(encoding="utf-8")
    assert "Crystal Corp." in notice_content, "NOTICE.md must attribute original Crystal Corp. authorship"
    assert "Johann Schleier-Smith" in notice_content, "NOTICE.md must credit Johann Schleier-Smith"
    assert "postgres-mcp" in notice_content, "NOTICE.md must reference postgres-mcp"


def test_contributing_defines_conventions_and_merge_policy() -> None:
    root = Path(__file__).resolve().parents[2]
    contributing_path = root / "CONTRIBUTING.md"

    assert contributing_path.is_file(), "CONTRIBUTING.md missing"
    content = contributing_path.read_text(encoding="utf-8")

    assert "Conventional Commits" in content or "conventional commits" in content.lower(), "Must define Conventional Commits"
    assert "squash" in content.lower(), "Must specify squash merge strategy"
    assert "feature/" in content and "bugfix/" in content, "Must document conventional branch categories"
    assert "TDD" in content or "test" in content.lower(), "Must require testing"


def test_readme_ghcr_commands_match_image() -> None:
    root = Path(__file__).resolve().parents[2]
    readme_en = (root / "README.md").read_text(encoding="utf-8")
    readme_pt = (root / "README.pt-BR.md").read_text(encoding="utf-8")

    for readme, lang in [(readme_en, "README.md"), (readme_pt, "README.pt-BR.md")]:
        assert "ghcr.io/diaszano/postgres-mcp" in readme, f"{lang} must reference ghcr.io/diaszano/postgres-mcp"
        assert "docker pull crystaldba/postgres-mcp" not in readme, f"{lang} must not reference docker pull crystaldba/postgres-mcp"


def test_no_crystaldba_publish_target() -> None:
    root = Path(__file__).resolve().parents[2]
    workflows = root / ".github" / "workflows"

    for wf in workflows.glob("*.yml"):
        content = wf.read_text(encoding="utf-8")
        assert "crystaldba/postgres-mcp" not in content, f"{wf.name} contains reference to upstream publish target"


def test_justfile_has_no_manual_release() -> None:
    root = Path(__file__).resolve().parents[2]
    justfile = (root / "justfile").read_text(encoding="utf-8")

    # Only automated CI releases are allowed, no local manual release recipe
    lines = [line.strip() for line in justfile.splitlines()]
    assert "release:" not in lines, "justfile must not have a manual 'release:' target"
