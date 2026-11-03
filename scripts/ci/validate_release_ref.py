#!/usr/bin/env python3
"""Validation utility for publish-only recovery operations."""

from __future__ import annotations

import argparse
import re
import sys
import tomllib
from pathlib import Path

STRICT_RELEASE_TAG_REGEX = re.compile(r"^v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


def validate_release_ref(tag: str, repo_root: Path | str = ".") -> dict[str, str]:
    """Validate release tag against pyproject.toml without modifying or bumping versions."""
    clean_tag = tag.strip()
    if not STRICT_RELEASE_TAG_REGEX.match(clean_tag):
        raise ValueError(f"Invalid release tag format: '{tag}'. Expected strict 'vX.Y.Z'.")

    expected_version = clean_tag[1:]

    root_path = Path(repo_root)
    pyproject_file = root_path / "pyproject.toml"
    if not pyproject_file.is_file():
        raise FileNotFoundError(f"pyproject.toml not found at {pyproject_file}")

    data = tomllib.loads(pyproject_file.read_bytes().decode("utf-8"))
    project_version = data.get("project", {}).get("version", "").strip()

    if project_version != expected_version:
        raise ValueError(f"Release tag '{clean_tag}' version '{expected_version}' does not match project version '{project_version}'.")

    return {
        "tag": clean_tag,
        "version": expected_version,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate release reference for publish-only recovery.")
    parser.add_argument("--tag", required=True, help="Existing release tag (e.g. v0.3.0)")
    parser.add_argument("--repo-root", default=".", help="Root directory containing pyproject.toml")

    args = parser.parse_args()

    try:
        res = validate_release_ref(tag=args.tag, repo_root=args.repo_root)
        print(f"✅ Validated release reference: tag={res['tag']}, version={res['version']}")
        return 0
    except Exception as exc:
        print(f"❌ Validation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
