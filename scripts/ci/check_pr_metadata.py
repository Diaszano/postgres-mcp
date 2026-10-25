#!/usr/bin/env python3
"""Validation utility for Pull Request title and source branch conventions.

Validates that pull requests adhere to Conventional Commits and branch naming
policies before triggering CI pipelines and release automation.
"""

from __future__ import annotations

import argparse
import os
import re
import sys

CONVENTIONAL_TITLE_REGEX = re.compile(
    r"^(feat|fix|docs|test|ci|build|perf|refactor|chore|revert)"
    r"(\([a-zA-Z0-9_\-\./]+\))?"
    r"(!)?:\s+[a-zA-Z0-9].*$"
)

CONVENTIONAL_BRANCH_REGEX = re.compile(r"^(feature|bugfix|hotfix|docs|test|ci|build|perf|refactor|chore|revert)/[a-zA-Z0-9_\-\.]+$")

DEPENDABOT_BRANCH_REGEX = re.compile(r"^dependabot/[a-zA-Z0-9_\-\./]+$")
ALLOWED_BOT_ACTORS = {"dependabot[bot]", "dependabot", "github-actions[bot]", "app/dependabot"}


def validate_pr(title: str, head_ref: str, actor: str) -> list[str]:
    """Validate PR title, source branch, and actor according to repo conventions.

    Returns a list of human-readable error messages. An empty list indicates success.
    """
    errors: list[str] = []

    clean_title = title.strip()
    clean_branch = head_ref.strip()

    if not clean_title:
        errors.append("PR title cannot be empty.")
    elif not CONVENTIONAL_TITLE_REGEX.match(clean_title):
        errors.append(
            f"PR title does not match Conventional Commits specification: '{clean_title}'. "
            "Expected format: '<type>(<optional-scope>): <description>' or '<type>!: <description>' "
            "with allowed types: feat, fix, docs, test, ci, build, perf, refactor, chore, revert."
        )

    if not clean_branch:
        errors.append("PR head branch cannot be empty.")
    else:
        if clean_branch.startswith("dependabot/"):
            if not DEPENDABOT_BRANCH_REGEX.match(clean_branch):
                errors.append(f"Invalid dependabot branch naming pattern: '{clean_branch}'.")
            if actor not in ALLOWED_BOT_ACTORS:
                errors.append(
                    f"Branch '{clean_branch}' suggests automated dependency update, "
                    f"but actor '{actor}' is not recognized as a dependency bot. "
                    f"Only dependabot bot is allowed to push to dependabot/* branches."
                )
        else:
            if not CONVENTIONAL_BRANCH_REGEX.match(clean_branch):
                errors.append(
                    f"Source branch name does not match conventional branch pattern: '{clean_branch}'. "
                    "Expected '<category>/<short-description>' with allowed categories: "
                    "feature, bugfix, hotfix, docs, test, ci, build, perf, refactor, chore, revert."
                )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate PR title and branch metadata conventions.")
    parser.add_argument("--title", default=os.getenv("PR_TITLE", ""), help="Pull request title")
    parser.add_argument("--head-ref", default=os.getenv("PR_HEAD_REF", ""), help="Pull request head source branch")
    parser.add_argument("--actor", default=os.getenv("GITHUB_ACTOR", ""), help="GitHub trigger actor")

    args = parser.parse_args()

    errors = validate_pr(title=args.title, head_ref=args.head_ref, actor=args.actor)
    if errors:
        print("❌ Pull Request metadata validation failed:\n", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    print("✅ Pull Request metadata conventions validated successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
