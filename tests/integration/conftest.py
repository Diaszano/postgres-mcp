"""Integration test fixtures for multi-database and HypoPG testing."""

import logging
import os
import secrets
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Generator

import docker
import psycopg
import pytest
from docker import errors as docker_errors
from psycopg import sql
from testcontainers.community.postgres import PostgresContainer

logger = logging.getLogger(__name__)

IMAGE = os.environ.get("MULTIDB_PG_IMAGE", "postgres-hypopg:16")
MCP_ROLE = "mcp_test_role"
VISIBLE_DATABASES = ("app_development", "app_testing", "analytics")
BLOCKED_DATABASE = "blocked_db"


@dataclass(frozen=True)
class MultiDbPostgres:
    host: str
    port: int
    admin_password: str
    mcp_password: str
    server_version: str
    mcp_role: str = MCP_ROLE
    visible_databases: tuple[str, ...] = VISIBLE_DATABASES
    blocked_database: str = BLOCKED_DATABASE

    def uri(self, user: str, dbname: str) -> str:
        password = self.mcp_password if user == MCP_ROLE else self.admin_password
        return f"postgresql://{user}:{password}@{self.host}:{self.port}/{dbname}"

    @property
    def mcp_bootstrap_uri(self) -> str:
        return self.uri(MCP_ROLE, "postgres")

    def admin(self, dbname: str = "postgres") -> psycopg.Connection:
        """Superuser connection, for fixture preparation only (never the MCP role)."""
        return psycopg.connect(self.uri("postgres", dbname), autocommit=True)


def _prepare(pg: MultiDbPostgres) -> None:
    with pg.admin() as conn:
        conn.execute(
            sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD {}").format(
                sql.Identifier(MCP_ROLE), sql.Literal(pg.mcp_password)
            )
        )
        conn.execute(sql.SQL("GRANT pg_read_all_stats TO {}").format(sql.Identifier(MCP_ROLE)))
        for name in (*VISIBLE_DATABASES, BLOCKED_DATABASE):
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
            conn.execute(sql.SQL("REVOKE CONNECT ON DATABASE {} FROM PUBLIC").format(sql.Identifier(name)))
        for name in VISIBLE_DATABASES:
            conn.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(sql.Identifier(name), sql.Identifier(MCP_ROLE)))
        conn.execute(sql.SQL("REVOKE CONNECT ON DATABASE {} FROM {}").format(sql.Identifier(BLOCKED_DATABASE), sql.Identifier(MCP_ROLE)))
        denied = conn.execute("SELECT has_database_privilege(%s, %s, 'CONNECT')", (MCP_ROLE, BLOCKED_DATABASE)).fetchone()
        assert denied == (False,), "MCP role must not be able to connect to blocked_db"
    for name in VISIBLE_DATABASES:
        marker = f"{name.removeprefix('app_')}_marker"
        with pg.admin(name) as conn:
            conn.execute(sql.SQL("CREATE TABLE {} (id int PRIMARY KEY, label text)").format(sql.Identifier(marker)))
            conn.execute(sql.SQL("INSERT INTO {} VALUES (1, {})").format(sql.Identifier(marker), sql.Literal(name)))
            conn.execute(sql.SQL("GRANT SELECT ON {} TO {}").format(sql.Identifier(marker), sql.Identifier(MCP_ROLE)))
    with pg.admin(BLOCKED_DATABASE) as conn:
        conn.execute("CREATE TABLE blocked_marker (id int)")
    for name in ("app_testing", "analytics"):
        with pg.admin(name) as conn:
            conn.execute("DROP EXTENSION IF EXISTS hypopg")
            conn.execute("DROP EXTENSION IF EXISTS pg_stat_statements")
    with pg.admin("app_development") as conn:
        conn.execute("CREATE EXTENSION IF NOT EXISTS pg_stat_statements")


@pytest.fixture(scope="session")
def multidb_postgres() -> Generator[MultiDbPostgres, None, None]:
    """Ephemeral PostgreSQL with four databases and a non-superuser MCP role. Fails (never skips) without Docker."""
    client = docker.from_env()
    client.ping()  # DockerException is a real failure, not a skip
    try:
        client.images.get(IMAGE)
    except docker_errors.ImageNotFound:
        msg = f"Required integration container image {IMAGE} was not found. Build it with hypopg before running integration tests."
        raise RuntimeError(msg) from None
    with _multidb_container(IMAGE) as pg:
        _prepare(pg)
        yield pg


@pytest.fixture(scope="session")
def hypopg_postgres(multidb_postgres: MultiDbPostgres) -> Generator[MultiDbPostgres, None, None]:
    """Require the HypoPG image and extension; missing extension or setup errors are failures, never skips."""
    with multidb_postgres.admin("app_development") as conn:
        conn.execute("CREATE EXTENSION IF NOT EXISTS hypopg")
        conn.execute(sql.SQL("GRANT SELECT ON hypopg_list_indexes TO {}").format(sql.Identifier(MCP_ROLE)))
    yield multidb_postgres


@contextmanager
def _multidb_container(image: str) -> Generator[MultiDbPostgres, None, None]:
    admin_password = secrets.token_urlsafe(24)
    container = PostgresContainer(
        image=image,
        username="postgres",
        password=admin_password,
        dbname="postgres",
        port=5432,
        driver=None,
    )
    container.with_command("-c shared_preload_libraries=pg_stat_statements -c pg_stat_statements.track=all")
    with container:
        host = container.get_container_host_ip()
        port = int(container.get_exposed_port(5432))
        pg = MultiDbPostgres(host, port, admin_password, secrets.token_urlsafe(24), "")
        with pg.admin() as conn:
            version_res = conn.execute("SHOW server_version").fetchone()
            object.__setattr__(pg, "server_version", version_res[0] if version_res else "")
        yield pg
