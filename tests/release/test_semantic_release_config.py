from __future__ import annotations

import tomllib
from pathlib import Path


def test_psr_contract_configuration() -> None:
    root = Path(__file__).resolve().parents[2]
    pyproject_path = root / "pyproject.toml"

    assert pyproject_path.is_file(), "pyproject.toml file missing"
    with pyproject_path.open("rb") as f:
        data = tomllib.load(f)

    tool_data = data.get("tool", {})
    assert "semantic_release" in tool_data, "pyproject.toml must contain [tool.semantic_release] section"

    cfg = tool_data["semantic_release"]
    assert cfg.get("allow_zero_version") is True, "allow_zero_version must be True"
    assert cfg.get("major_on_zero") is False, "major_on_zero must be False (breaking changes on 0.x bump minor, not 1.0.0)"
    assert cfg.get("tag_format") == "v{version}", "tag_format must be 'v{version}'"
    assert cfg.get("commit_parser") == "conventional", "commit_parser must be 'conventional'"
    assert "pyproject.toml:project.version" in cfg.get("version_toml", []), "version_toml must target pyproject.toml:project.version"
    assert "[skip ci]" in cfg.get("commit_message", ""), "commit_message must include [skip ci] to prevent CI loops"

    branches = cfg.get("branches", {})
    assert "main" in branches, "Must configure main branch in [tool.semantic_release.branches.main]"
    assert branches["main"].get("prerelease") is False, "main branch must not be prerelease"


def test_no_manual_tagging_in_justfile() -> None:
    root = Path(__file__).resolve().parents[2]
    justfile_path = root / "justfile"

    if justfile_path.is_file():
        content = justfile_path.read_text(encoding="utf-8")
        # Ensure no manual release publication shortcuts
        assert "gh release create" not in content, "justfile must not create GitHub releases manually"
        assert "git tag -a" not in content and "git tag v" not in content, "justfile must not create manual git release tags"
        assert "release-preview" in content, "justfile must provide 'release-preview' recipe"
