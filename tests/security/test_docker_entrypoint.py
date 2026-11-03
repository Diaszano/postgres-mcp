import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ENTRYPOINT = ROOT / "docker-entrypoint.sh"


@pytest.mark.parametrize("remap", ["false", "true"])
def test_entrypoint_preserves_unchanged_arguments(tmp_path, remap):
    args = ["--option=value\n\n", "", "host=localhost dbname=app\n", "postgresql://db.example/app\n"]
    result, captured = _run_entrypoint(
        tmp_path,
        args,
        env={"DATABASE_URI": "host=localhost dbname=app\n", "DATABASE_DOCKER_REMAP_LOCALHOST": remap},
        ping_script="#!/bin/sh\nexit 0\n",
    )
    assert result.returncode == 0
    assert captured == {"argv": args, "database_uri": "host=localhost dbname=app\n"}


def _run_entrypoint(tmp_path, args, *, env=None, ping_script=None):
    capture = tmp_path / "captured.json"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    postgres_mcp = fake_bin / "postgres-mcp"
    postgres_mcp.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, sys\n"
        "with open(os.environ['CAPTURE_FILE'], 'w') as f:\n"
        "    json.dump({'argv': sys.argv[1:], 'database_uri': os.environ.get('DATABASE_URI')}, f)\n"
    )
    postgres_mcp.chmod(0o755)
    path = str(fake_bin)
    if ping_script:
        ping = fake_bin / "ping"
        ping.write_text(ping_script)
        ping.chmod(0o755)
    run_env = os.environ.copy()
    run_env.update({"PATH": path + os.pathsep + run_env["PATH"], "CAPTURE_FILE": str(capture)})
    if env:
        run_env.update(env)
    result = subprocess.run(
        ["bash", str(ENTRYPOINT), "postgres-mcp", *args],
        env=run_env,
        text=True,
        capture_output=True,
        check=False,
    )
    captured = json.loads(capture.read_text()) if capture.exists() else None
    return result, captured


def test_entrypoint_never_logs_database_uri(tmp_path):
    uri = "postgresql://user%40host:p%3Ass%40word@db.example:5432/app?options=hello%20world"
    result, captured = _run_entrypoint(
        tmp_path,
        [uri],
        env={"DATABASE_URI": uri},
    )

    assert result.returncode == 0
    assert uri not in result.stdout + result.stderr
    assert captured == {"argv": [uri], "database_uri": uri}


@pytest.mark.parametrize("suffix", ["", "\n\n"])
def test_entrypoint_remapping_is_opt_in(tmp_path, suffix):
    uri = "postgresql://user%40localhost:p%3Ass@localhost:5432/app?application_name=localhost" + suffix
    ping = '#!/bin/sh\ncase "$*" in *host.docker.internal*) exit 0;; *) exit 1;; esac\n'

    default_dir = tmp_path / "default"
    default_dir.mkdir()
    default, captured_default = _run_entrypoint(
        default_dir,
        [uri],
        env={"DATABASE_URI": uri},
        ping_script=ping,
    )
    assert default.returncode == 0
    assert captured_default == {"argv": [uri], "database_uri": uri}

    enabled_dir = tmp_path / "enabled"
    enabled_dir.mkdir()
    enabled, captured_enabled = _run_entrypoint(
        enabled_dir,
        [uri],
        env={"DATABASE_URI": uri, "DATABASE_DOCKER_REMAP_LOCALHOST": "true"},
        ping_script=ping,
    )
    remapped = uri.replace("@localhost:", "@host.docker.internal:")
    assert enabled.returncode == 0
    assert uri not in enabled.stdout + enabled.stderr
    assert remapped not in enabled.stdout + enabled.stderr
    assert captured_enabled == {"argv": [remapped], "database_uri": remapped}

    invalid_dir = tmp_path / "invalid"
    invalid_dir.mkdir()
    invalid, _ = _run_entrypoint(
        invalid_dir,
        [uri],
        env={"DATABASE_DOCKER_REMAP_LOCALHOST": "yes"},
    )
    assert invalid.returncode != 0
    assert "yes" not in invalid.stdout + invalid.stderr
