"""Tests for Homebrew tap cask generator and updater."""

from __future__ import annotations

from scripts.release.update_homebrew_tap import generate_cask_content


def test_generate_cask_content_structure() -> None:
    checksums = {
        "darwin_amd64": "1111111111111111111111111111111111111111111111111111111111111111",
        "darwin_arm64": "2222222222222222222222222222222222222222222222222222222222222222",
        "linux_amd64": "3333333333333333333333333333333333333333333333333333333333333333",
        "linux_arm64": "4444444444444444444444444444444444444444444444444444444444444444",
    }
    cask_text = generate_cask_content("0.4.2", checksums)

    assert 'cask "pgscope" do' in cask_text
    assert 'version "0.4.2"' in cask_text
    assert "on_macos do" in cask_text
    assert "on_intel do" in cask_text
    assert "on_arm do" in cask_text
    assert "on_linux do" in cask_text
    assert checksums["darwin_amd64"] in cask_text
    assert checksums["darwin_arm64"] in cask_text
    assert checksums["linux_amd64"] in cask_text
    assert checksums["linux_arm64"] in cask_text
    assert 'binary "pgscope"' in cask_text
    assert "https://github.com/Diaszano/pgscope/releases/download/v#{version}/" in cask_text
