from __future__ import annotations

import re
from pathlib import Path

import yaml

HEX_40_REGEX = re.compile(r"@[0-9a-f]{40}$")


def test_security_policy_content() -> None:
    root = Path(__file__).resolve().parents[2]
    sec_file = root / "SECURITY.md"

    assert sec_file.is_file(), "SECURITY.md policy file missing"
    content = sec_file.read_text(encoding="utf-8").lower()

    assert "expiry" in content or "expiration" in content, "SECURITY.md must require expiration dates for vulnerability waivers"
    assert "sbom" in content, "SECURITY.md must define Software Bill of Materials (SBOM) policy"
    assert "provenance" in content, "SECURITY.md must define build provenance attestation policy"
    assert "vulnerability" in content, "SECURITY.md must outline vulnerability reporting"


def test_security_workflow_permissions() -> None:
    root = Path(__file__).resolve().parents[2]
    sec_workflow = root / ".github" / "workflows" / "security.yml"

    assert sec_workflow.is_file(), ".github/workflows/security.yml workflow missing"
    raw_text = sec_workflow.read_text(encoding="utf-8")
    content = yaml.load(raw_text, Loader=yaml.BaseLoader)

    # Must be read-only
    top_perms = content.get("permissions", {})
    assert top_perms.get("contents") == "read", "security.yml must specify top-level 'contents: read'"

    # Must be pinned to 40-character commit SHAs
    for match in re.finditer(r"uses:\s+([^\s]+)", raw_text):
        action_ref = match.group(1).strip()
        if not action_ref.startswith("./"):
            assert HEX_40_REGEX.search(action_ref), f"Action '{action_ref}' in security.yml not pinned to 40-char SHA"

    # Must not contain release/publish commands
    assert "gh release" not in raw_text, "security.yml must not execute release publication"
    assert "git push" not in raw_text, "security.yml must not push git commits or tags"
