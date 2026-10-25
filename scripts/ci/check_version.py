#!/usr/bin/env python3
"""Verification utility for package release version metadata.

Validates that pyproject.toml version adheres to Semantic Versioning and matches
any git tag requested for release publication.
"""

from __future__ import annotations

import argparse
import re
import sys
import tomllib
from pathlib import Path

SEMVER_REGEX = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(-((0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(\.(0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(\+([0-9a-zA-Z-]+(\.[0-9a-zA-Z-]+)*))?$"
)


def get_pyproject_version(project_dir: Path) -> str:
    """Read and return project.version from pyproject.toml."""
    pyproject_file = project_dir / "pyproject.toml"
    if not pyproject_file.is_file():
        raise FileNotFoundError(f"pyproject.toml not found at {pyproject_file}")

    with pyproject_file.open("rb") as f:
        data = tomllib.load(f)

    project_data = data.get("project", {})
    version = project_data.get("version")
    if not version:
        raise ValueError("Missing 'project.version' field in pyproject.toml")

    return str(version).strip()


def check_package_version(tag: str | None = None, project_dir: Path | str = ".") -> str:
    """Validate project version and optional release tag.

    Returns the normalized project version on success; raises ValueError on mismatch or invalid format.
    """
    path = Path(project_dir).resolve()
    version = get_pyproject_version(path)

    if not SEMVER_REGEX.match(version):
        raise ValueError(f"Invalid semantic version in pyproject.toml: '{version}'")

    if tag is not None:
        clean_tag = tag.strip()
        normalized_tag = clean_tag[1:] if clean_tag.startswith("v") else clean_tag

        if not SEMVER_REGEX.match(normalized_tag):
            raise ValueError(f"Invalid semantic version in release tag: '{tag}'")

        if normalized_tag != version:
            raise ValueError(f"Version mismatch: git tag '{tag}' (normalized: '{normalized_tag}') does not match pyproject.toml version '{version}'.")

    return version


def main() -> int:
    parser = argparse.ArgumentParser(description="Check package version against pyproject.toml and release tags.")
    parser.add_argument("--tag", default=None, help="Optional git release tag (e.g., v0.3.0)")
    parser.add_argument("--project-dir", default=".", help="Path to project directory containing pyproject.toml")

    args = parser.parse_args()

    try:
        ver = check_package_version(tag=args.tag, project_dir=args.project_dir)
        print(f"✅ Package version verified: {ver}")
        return 0
    except Exception as exc:
        print(f"❌ Version verification failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
