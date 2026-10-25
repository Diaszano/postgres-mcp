"""Integration test fixtures for multi-database and HypoPG testing."""

import logging
import os
import secrets
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Generator

import docker
import psycopg
import pytest
from docker import errors as docker_errors
from psycopg import sql

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
    with _multidb_container(client, IMAGE) as pg:
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
def _multidb_container(client: docker.DockerClient, image: str) -> Generator[MultiDbPostgres, None, None]:
    admin_password = secrets.token_urlsafe(24)
    container = client.containers.run(
        image,
        name=f"postgres-mcp-multidb-{secrets.token_hex(4)}",
        environment={"POSTGRES_PASSWORD": admin_password},
        ports={"5432/tcp": ("127.0.0.1", 0)},
        command=["-c", "shared_preload_libraries=pg_stat_statements", "-c", "pg_stat_statements.track=all"],
        detach=True,
    )
    try:
        deadline = time.time() + 90
        while True:
            container.reload()
            port_info = container.ports.get("5432/tcp")
            if port_info:
                port = int(port_info[0]["HostPort"])
                try:
                    psycopg.connect(f"postgresql://postgres:{admin_password}@127.0.0.1:{port}/postgres", connect_timeout=2).close()
                    break
                except psycopg.OperationalError:
                    pass
            if time.time() > deadline:
                raise RuntimeError(f"PostgreSQL did not become ready; container logs tail:\n{container.logs().decode()[-1500:]}")
            time.sleep(1)
        pg = MultiDbPostgres("127.0.0.1", port, admin_password, secrets.token_urlsafe(24), "")
        with pg.admin() as conn:
            version_res = conn.execute("SHOW server_version").fetchone()
            object.__setattr__(pg, "server_version", version_res[0] if version_res else "")
        yield pg
    finally:
        container.stop()
        container.remove(v=True)
