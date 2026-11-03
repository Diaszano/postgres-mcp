from __future__ import annotations

import os
import subprocess
from pathlib import Path


def test_scan_script_structure() -> None:
    root = Path(__file__).resolve().parents[2]
    script_path = root / "scripts" / "ci" / "scan_image.sh"

    assert script_path.is_file(), "scripts/ci/scan_image.sh missing"
    assert os.access(script_path, os.X_OK), "scan_image.sh must be executable"

    content = script_path.read_text(encoding="utf-8")
    assert "set -euo pipefail" in content, "Script must enforce strict bash error handling"
    assert "HIGH,CRITICAL" in content, "Scanner must check HIGH and CRITICAL vulnerabilities"
    assert "--exit-code 1" in content, "Scanner must fail closed with --exit-code 1 on findings"
    assert "linux/amd64" in content, "Scanner must scan linux/amd64 architecture"
    assert "linux/arm64" in content, "Scanner must scan linux/arm64 architecture"


def test_scan_script_fails_on_missing_or_invalid_image() -> None:
    root = Path(__file__).resolve().parents[2]
    script_path = root / "scripts" / "ci" / "scan_image.sh"

    # Missing argument
    res_no_args = subprocess.run([str(script_path)], capture_output=True, text=True)
    assert res_no_args.returncode != 0, "Script must fail when called without image reference"

    # Missing sha256 digest
    res_no_digest = subprocess.run([str(script_path), "ghcr.io/diaszano/postgres-mcp:latest"], capture_output=True, text=True)
    assert res_no_digest.returncode != 0, "Script must require immutable @sha256: digest"
    assert "sha256" in res_no_digest.stderr.lower() or "digest" in res_no_digest.stderr.lower()
