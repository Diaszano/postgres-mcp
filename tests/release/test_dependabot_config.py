from __future__ import annotations

from pathlib import Path

import yaml


def test_dependabot_config_structure() -> None:
    root = Path(__file__).resolve().parents[2]
    config_file = root / ".github" / "dependabot.yml"

    assert config_file.is_file(), ".github/dependabot.yml file missing"
    data = yaml.safe_load(config_file.read_text(encoding="utf-8"))

    assert data.get("version") == 2, "Dependabot version must be 2"
    updates = data.get("updates", [])
    assert len(updates) >= 3, f"Expected at least 3 update configs, found: {len(updates)}"

    ecosystems = {item["package-ecosystem"] for item in updates}
    assert {"uv", "github-actions", "docker"} <= ecosystems, f"Expected ecosystems uv, github-actions, docker. Found: {ecosystems}"

    for update in updates:
        ecosystem = update["package-ecosystem"]
        schedule = update.get("schedule", {})
        assert schedule.get("interval") == "weekly", f"Ecosystem '{ecosystem}' must use weekly interval"

        limit = int(update.get("open-pull-requests-limit", 0))
        assert 1 <= limit <= 10, f"Ecosystem '{ecosystem}' must bound open-pull-requests-limit (1-10), got {limit}"


def test_contributing_mentions_dependabot_review() -> None:
    root = Path(__file__).resolve().parents[2]
    contributing_file = root / "CONTRIBUTING.md"

    assert contributing_file.is_file(), "CONTRIBUTING.md missing"
    content = contributing_file.read_text(encoding="utf-8")
    assert "dependabot" in content.lower(), "CONTRIBUTING.md must describe how dependabot PRs are managed"
