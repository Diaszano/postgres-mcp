from __future__ import annotations

import pytest

from scripts.ci.validate_release import validate_release_baseline


def test_duplicate_tags_rejected() -> None:
    with pytest.raises(ValueError, match="Duplicate release tags detected"):
        validate_release_baseline("0.3.0", ["v0.3.0", "v0.3.0"])


def test_valid_baseline_accepts_clean_ancestry() -> None:
    # Existing tags prior to or matching current project version
    validate_release_baseline("0.3.0", ["v0.1.0", "v0.2.0", "v0.3.0"])
    validate_release_baseline("0.3.0", ["v0.2.0"])
    validate_release_baseline("0.3.0", [])


def test_tag_ahead_of_project_version_rejected() -> None:
    # Remote tag cannot be higher than local project version without proper checkout
    with pytest.raises(ValueError, match="is ahead of project version"):
        validate_release_baseline("0.3.0", ["v0.1.0", "v0.4.0"])


def test_malformed_tags_in_baseline_ignored_or_rejected() -> None:
    with pytest.raises(ValueError, match="Invalid tag format in release history"):
        validate_release_baseline("0.3.0", ["v0.1.0", "experimental-tag"])
