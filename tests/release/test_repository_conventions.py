"""Tests verifying repository build-context (.dockerignore) and editor conventions."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_docker_context_keeps_runtime_inputs():
    """Verify .dockerignore keeps required files for Docker build."""
    dockerignore_path = REPO_ROOT / ".dockerignore"
    assert dockerignore_path.exists(), ".dockerignore must exist"
    ignore = dockerignore_path.read_text(encoding="utf-8").splitlines()

    # Required inputs must NOT be ignored
    for required in ["uv.lock", "pyproject.toml", "src", "docker-entrypoint.sh"]:
        assert required not in ignore, f"'{required}' must not be ignored in .dockerignore"


def test_no_secrets_in_image_context():
    """Verify .dockerignore excludes sensitive paths, build artifacts, and virtual environments."""
    dockerignore_path = REPO_ROOT / ".dockerignore"
    assert dockerignore_path.exists(), ".dockerignore must exist"
    content = dockerignore_path.read_text(encoding="utf-8")

    # Sensitive files and build artifacts must be excluded
    for pattern in [".git", ".venv", "dist", ".env"]:
        assert pattern in content, f"Pattern '{pattern}' must be present in .dockerignore"


def test_editorconfig_and_gitattributes_present():
    """Verify .editorconfig and .gitattributes exist and standardize text formatting."""
    editorconfig = REPO_ROOT / ".editorconfig"
    assert editorconfig.exists(), ".editorconfig must exist"
    ec_content = editorconfig.read_text(encoding="utf-8")
    assert "charset = utf-8" in ec_content or "charset=utf-8" in ec_content
    assert "end_of_line = lf" in ec_content or "end_of_line=lf" in ec_content

    gitattributes = REPO_ROOT / ".gitattributes"
    assert gitattributes.exists(), ".gitattributes must exist"
    ga_content = gitattributes.read_text(encoding="utf-8")
    assert "* text=auto" in ga_content or "text=auto" in ga_content
