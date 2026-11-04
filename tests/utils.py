import logging
from pathlib import Path
from typing import Generator
from typing import Tuple

import docker
import pytest
from docker import errors as docker_errors
from testcontainers.community.postgres import PostgresContainer

logger = logging.getLogger(__name__)


def ensure_hypopg_image(client: docker.DockerClient, version: str) -> str:
    """Ensure custom Docker image with HypoPG exists, building if necessary."""
    pg_version = version.split(":")[1] if ":" in version else version
    custom_image_name = f"postgres-hypopg:{pg_version}"
    current_dir = Path(__file__).parent.absolute()

    try:
        client.images.get(custom_image_name)
        logger.info(f"Using existing Docker image: {custom_image_name}")
    except docker_errors.ImageNotFound:
        logger.info(f"Building custom Docker image: {custom_image_name}")
        try:
            dockerfile_path = current_dir / "Dockerfile.postgres-hypopg"
            if not dockerfile_path.exists():
                logger.error(f"Dockerfile not found at {dockerfile_path}")
                pytest.skip(f"Required Dockerfile not found: {dockerfile_path}")

            client.images.build(
                path=str(current_dir),
                dockerfile="Dockerfile.postgres-hypopg",
                buildargs={"PG_VERSION": pg_version, "PG_MAJOR": pg_version},
                tag=custom_image_name,
                rm=True,
            )
            logger.info(f"Successfully built image {custom_image_name}")
        except Exception as e:
            logger.error(f"Failed to build Docker image: {e}")
            pytest.skip(f"Failed to build Docker image: {e}")

    return custom_image_name


def create_postgres_container(version: str) -> Generator[Tuple[str, str], None, None]:
    """Create a PostgreSQL container of specified version using Testcontainers and return its connection string."""
    try:
        client = docker.from_env()
        client.ping()
    except (docker_errors.DockerException, ConnectionError):
        pytest.skip("Docker is not available")

    custom_image_name = ensure_hypopg_image(client, version)

    postgres_password = "test_password"
    postgres_db = "test_db"

    container = PostgresContainer(
        image=custom_image_name,
        username="postgres",
        password=postgres_password,
        dbname=postgres_db,
        port=5432,
        driver=None,
    )
    container.with_command(
        "-c shared_preload_libraries=pg_stat_statements -c pg_stat_statements.track=all -c log_min_messages=info -c log_statement=all"
    )
    container.with_env("POSTGRES_HOST_AUTH_METHOD", "trust")

    try:
        with container:
            connection_string = container.get_connection_url(driver=None)
            logger.info(f"PostgreSQL container ready, connection string: {connection_string}")
            yield connection_string, version
    except Exception as e:
        logger.error(f"Error running PostgreSQL Testcontainer: {e}")
        raise
