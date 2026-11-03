#!/usr/bin/env python3
"""Validation and calculation utility for Semantic Release versioning and tags."""

from __future__ import annotations

import argparse
import re
import sys

STRICT_RELEASE_TAG_REGEX = re.compile(r"^v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


def validate_release_tag(tag: str, project_version: str) -> None:
    """Validate that a release tag follows strict 'vX.Y.Z' stable SemVer and matches project_version."""
    clean_tag = tag.strip()
    if not clean_tag.startswith("v"):
        raise ValueError(f"Release tag must start with 'v' (e.g., v0.3.0), got: '{tag}'")

    version_part = clean_tag[1:]
    if any(pre in version_part.lower() for pre in ("rc", "alpha", "beta", "dev", "preview", "-", "+")):
        raise ValueError(f"Prerelease suffixes are not permitted for stable releases: '{tag}'")

    if not STRICT_RELEASE_TAG_REGEX.match(clean_tag):
        raise ValueError(f"Invalid semantic version format in release tag: '{tag}'")

    if version_part != project_version.strip():
        raise ValueError(f"Tag version '{version_part}' does not match expected project version '{project_version.strip()}'.")


def calculate_next_version(current_version: str, commit_messages: list[str], major_on_zero: bool = False) -> str | None:
    """Calculate the next semantic version based on Conventional Commit messages.

    Respects allow_zero_version policy: when major_on_zero is False and major is 0,
    breaking changes bump minor rather than major.
    """
    parts = [int(p) for p in current_version.strip().split(".")]
    if len(parts) != 3:
        raise ValueError(f"Invalid SemVer base version: {current_version}")

    major, minor, patch = parts

    has_breaking = False
    has_feature = False
    has_fix = False

    for msg in commit_messages:
        clean = msg.strip()
        if not clean or "[skip ci]" in clean:
            continue

        header = clean.split("\n", 1)[0].strip()

        # Check for breaking change indicator
        if re.match(r"^[a-zA-Z]+(\([^\)]+\))?!:\s+", header) or "BREAKING CHANGE:" in clean or "BREAKING-CHANGE:" in clean:
            has_breaking = True
        elif re.match(r"^feat(\([^\)]+\))?:\s+", header):
            has_feature = True
        elif re.match(r"^fix(\([^\)]+\))?:\s+", header):
            has_fix = True

    if has_breaking:
        if major == 0 and not major_on_zero:
            return f"0.{minor + 1}.0"
        return f"{major + 1}.0.0"

    if has_feature:
        return f"{major}.{minor + 1}.0"

    if has_fix:
        return f"{major}.{minor}.{patch + 1}"

    return None


def validate_release_baseline(project_version: str, reachable_tags: list[str]) -> None:
    """Validate git reachable tags against project version to ensure idempotent bootstrap."""
    if len(reachable_tags) != len(set(reachable_tags)):
        raise ValueError("Duplicate release tags detected in repository history.")

    proj_parts = tuple(int(p) for p in project_version.strip().split("."))
    if len(proj_parts) != 3:
        raise ValueError(f"Invalid project SemVer: {project_version}")

    for tag in reachable_tags:
        clean_tag = tag.strip()
        if not STRICT_RELEASE_TAG_REGEX.match(clean_tag):
            raise ValueError(f"Invalid tag format in release history: '{tag}'")

        tag_parts = tuple(int(p) for p in clean_tag[1:].split("."))
        if tag_parts > proj_parts:
            raise ValueError(
                f"Reachable tag '{tag}' is ahead of project version '{project_version}'. Ensure local branch is aligned with the latest release."
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate release tag and SemVer rules.")
    parser.add_argument("--tag", required=True, help="Release tag to validate (e.g., v0.3.0)")
    parser.add_argument("--version", required=True, help="Expected project version (e.g., 0.3.0)")

    args = parser.parse_args()

    try:
        validate_release_tag(tag=args.tag, project_version=args.version)
        print(f"✅ Release tag '{args.tag}' is valid and matches project version '{args.version}'.")
        return 0
    except Exception as exc:
        print(f"❌ Validation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
