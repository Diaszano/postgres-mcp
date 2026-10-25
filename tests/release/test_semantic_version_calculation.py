from __future__ import annotations

import re

import pytest

from scripts.ci.validate_release import validate_release_tag


def test_validate_release_tag_valid() -> None:
    validate_release_tag("v0.3.0", "0.3.0")
    validate_release_tag("v0.3.1", "0.3.1")
    validate_release_tag("v1.0.0", "1.0.0")


@pytest.mark.parametrize(
    "tag,version,expected_substr",
    [
        ("0.3.0", "0.3.0", "Release tag must start with 'v'"),
        ("v0.3", "0.3.0", "Invalid semantic version format"),
        ("v0.3.1rc1", "0.3.1", "Prerelease suffixes are not permitted for stable releases"),
        ("v0.3.1-beta", "0.3.1", "Prerelease suffixes are not permitted for stable releases"),
        ("v0.3.2", "0.3.1", "Tag version '0.3.2' does not match expected project version '0.3.1'"),
        ("invalid-tag", "0.3.0", "Release tag must start with 'v'"),
    ],
)
def test_validate_release_tag_invalid(tag: str, version: str, expected_substr: str) -> None:
    with pytest.raises(ValueError, match=re.escape(expected_substr)):
        validate_release_tag(tag, version)


def test_isolated_git_commit_classification() -> None:
    from scripts.ci.validate_release import calculate_next_version

    # In 0.x mode with major_on_zero=False:
    # fix -> patch
    # feat -> minor
    # feat! / breaking -> minor
    # docs/chore/skip ci -> None (no bump)

    base = "0.3.0"
    assert calculate_next_version(base, ["fix: fix bug"]) == "0.3.1"
    assert calculate_next_version(base, ["feat: add feature"]) == "0.4.0"
    assert calculate_next_version(base, ["feat!: breaking feature"]) == "0.4.0"
    assert calculate_next_version(base, ["fix!: breaking fix"]) == "0.4.0"
    assert calculate_next_version(base, ["docs: update readme", "chore(release): 0.3.0 [skip ci]"]) is None
    assert calculate_next_version(base, ["chore: clean build", "ci: update actions"]) is None
