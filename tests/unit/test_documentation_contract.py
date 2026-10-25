"""Unit tests verifying documentation accuracy, environment variable contracts, client snippet safety, and EN/pt-BR parity."""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

SUPPORTED_ENV_VARS = {
    "DATABASE_URI",
    "DATABASE_AUTO_DISCOVER",
    "DATABASE_ALLOWED_DATABASES",
    "DATABASE_EXCLUDED_DATABASES",
    "DATABASE_DEFAULT_DATABASE",
    "DATABASE_DISCOVERY_TTL_SECONDS",
    "DATABASE_MAX_POOLS",
    "DATABASE_POOL_MAX_SIZE",
    "DATABASE_POOL_IDLE_SECONDS",
    "DATABASE_QUERY_GUARDRAILS_ENABLED",
    "DATABASE_QUERY_DEFAULT_MAX_ROWS",
    "DATABASE_QUERY_HARD_MAX_ROWS",
    "DATABASE_QUERY_DEFAULT_TIMEOUT_SECONDS",
    "DATABASE_QUERY_HARD_TIMEOUT_SECONDS",
    "DATABASE_QUERY_MAX_RESULT_BYTES",
    "DATABASE_QUERY_MAX_CONCURRENCY",
    "DATABASE_PAGINATION_ENABLED",
    "DATABASE_PAGINATION_DEFAULT_PAGE_SIZE",
    "DATABASE_PAGINATION_MAX_PAGE_SIZE",
    "DATABASE_PAGINATION_CURSOR_TTL_SECONDS",
    "DATABASE_PAGINATION_MAX_ACTIVE_CURSORS",
    "DATABASE_METRICS_ENABLED",
    "DATABASE_DOCKER_REMAP_LOCALHOST",
}


def test_documented_env_keys_match_parser():
    """Extract environment variable keys from docs and verify they match actual parser keys."""
    docs = [
        REPO_ROOT / "README.md",
        REPO_ROOT / "README.pt-BR.md",
        REPO_ROOT / "docs" / "security-deployment.md",
        REPO_ROOT / "docs" / "migration-query-guardrails.md",
    ]
    for doc in docs:
        assert doc.exists(), f"Expected documentation file {doc} to exist"
        content = doc.read_text(encoding="utf-8")
        matches = set(re.findall(r"\bDATABASE_[A-Z0-9_]+\b", content))
        # Ignore error code strings that happen to start with DATABASE_
        var_candidates = {m for m in matches if not m.endswith("_ERROR") and m not in {"DATABASE_UNAVAILABLE", "DATABASE_NOT_ALLOWED"}}
        for var in var_candidates:
            assert var in SUPPORTED_ENV_VARS, f"Documented variable '{var}' in {doc.name} is not recognized by parsers"


def test_client_samples_have_no_secrets():
    """Verify client snippets in README and examples/mcp-clients.md contain no hardcoded passwords."""
    targets = [
        REPO_ROOT / "README.md",
        REPO_ROOT / "README.pt-BR.md",
        REPO_ROOT / "examples" / "mcp-clients.md",
    ]
    for target in targets:
        assert target.exists(), f"File {target} must exist"
        content = target.read_text(encoding="utf-8")
        # Check for real passwords in postgresql:// uris
        dangerous_uris = re.findall(r"postgresql://[^:]+:([a-zA-Z0-9_-]{6,})@", content)
        # Placeholders like user:password or user:secret or user:${VAR} are fine, but no actual credentials
        real_looking = [p for p in dangerous_uris if p.lower() not in {"password", "secret", "mcp_password", "admin_password"}]
        assert not real_looking, f"Potential hardcoded credentials found in {target.name}: {real_looking}"


def test_versioned_contract_examples():
    """Verify query budgets, cursor pagination contracts, and fetch_query_page are documented."""
    migration_doc = REPO_ROOT / "docs" / "migration-query-guardrails.md"
    assert migration_doc.exists()
    content = migration_doc.read_text(encoding="utf-8")

    assert "fetch_query_page" in content
    assert "max_rows" in content
    assert "timeout_seconds" in content
    assert "cursor" in content
    assert "TTL" in content or "ttl" in content
    assert "best-effort" in content or "no snapshot" in content.lower()


def test_english_portuguese_parity():
    """Ensure both README.md and README.pt-BR.md describe query budgets, pagination, and guardrails."""
    en_readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    pt_readme = (REPO_ROOT / "README.pt-BR.md").read_text(encoding="utf-8")

    terms = [
        ("DATABASE_QUERY_GUARDRAILS_ENABLED", "DATABASE_QUERY_GUARDRAILS_ENABLED"),
        ("DATABASE_PAGINATION_ENABLED", "DATABASE_PAGINATION_ENABLED"),
        ("fetch_query_page", "fetch_query_page"),
    ]
    for en_term, pt_term in terms:
        assert en_term in en_readme, f"'{en_term}' missing from English README"
        assert pt_term in pt_readme, f"'{pt_term}' missing from Portuguese README"
