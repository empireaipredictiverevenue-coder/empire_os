"""Original EmpireOS V4.1 real Redis 8 Unix-socket acceptance.

Explicit opt-in uses a temporary extracted Ubuntu package. No installation,
Redis Cloud, production Redis, settlement or autonomous execution.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess

import pytest

ROOT=Path(__file__).resolve().parents[1]
SHELL=ROOT/"scripts/rehearse_predictive_cloud_v4_real_redis_20261024.sh"
HARNESS=ROOT/"scripts/rehearse_predictive_cloud_v4_real_redis_20261024.py"


def test_real_redis_wrapper_requires_temporary_bin_and_explicit_auth():
    code=SHELL.read_text()
    for guard in (
        "V4_REAL_REDIS_SERVER_BINARY_NOT_PROVIDED",
        "V4_REFUSED_UNREVIEWED_REDIS_SERVER_BINARY_PATH",
        "V4_REFUSED_UNREVIEWED_REDIS_LIBRARY_PATH",
        "V4_UNIX_SOCKET_PERMISSIONS_NOT_PRIVATE",
        "--port 0",
        "--unixsocketperm 700",
        "--appendonly no",
        '--save ""',
        "--maxmemory 32mb",
        "--maxmemory-policy noeviction",
        "--daemonize no",
        "trap cleanup EXIT",
    ):
        assert guard in code
    assert "docker" not in code.lower()
    assert "systemctl" not in code.lower()
    assert "apt install" not in code.lower()


def test_real_redis_harness_never_uses_network_or_production_db():
    code=HARNESS.read_text()
    assert "socket.AF_UNIX" in code
    assert "socket.AF_INET" not in code
    assert "import redis" not in code
    assert "V4_REFUSED_NON_EPHEMERAL_REDIS_UNIX_SOCKET" in code
    assert '"tcp_port":0' in code
    assert '"redis_cloud_connected":False' in code
    assert '"production_empiredb_touched":False' in code
    assert '"real_latency_slo_verified":False' in code
    assert '"money_moved":False' in code
    assert "concurrent_independent_writer_connections" in code


def test_real_redis_wrapper_refuses_ambient_or_wrong_server():
    env=dict(os.environ)
    env.pop("EMPIRE_V4_REDIS_SERVER_BIN",None)
    env.pop("EMPIRE_V4_REDIS_LIBRARY_DIR",None)
    run=subprocess.run(["bash",str(SHELL)],cwd=ROOT,env=env,
                       capture_output=True,text=True,timeout=5)
    assert run.returncode==9
    assert "V4_REAL_REDIS_SERVER_BINARY_NOT_PROVIDED" in run.stdout
    env["EMPIRE_V4_REDIS_SERVER_BIN"]="/usr/bin/true"
    env["EMPIRE_V4_REDIS_LIBRARY_DIR"]="/tmp"
    run=subprocess.run(["bash",str(SHELL)],cwd=ROOT,env=env,
                       capture_output=True,text=True,timeout=5)
    assert run.returncode==9
    assert "V4_REFUSED_UNREVIEWED_REDIS_SERVER_BINARY_PATH" in run.stdout


@pytest.mark.skipif(
    not (os.environ.get("EMPIRE_V4_REDIS_SERVER_BIN") and
         os.environ.get("EMPIRE_V4_REDIS_LIBRARY_DIR")),
    reason="real Redis fixture binaries not supplied (no system install permitted)",
)
def test_genuine_redis8_lua_concurrent_writes_and_ttl():
    result=subprocess.run(["bash",str(SHELL)],cwd=ROOT,env=os.environ.copy(),
                          capture_output=True,text=True,timeout=40)
    assert result.returncode==0,result.stdout[-4500:]+"\n"+result.stderr[-1800:]
    output=result.stdout.splitlines()
    message=next((json.loads(line) for line in output
                  if line.startswith('{"concurrent_independent_writer_connections":')),None)
    assert message is not None
    assert message["status"]=="REAL_LOCAL_REDIS8_V4_HOTPATH_PASS"
    assert message["redis_version"].startswith("8.")
    assert message["tcp_port"]==0
    assert message["persistence_enabled"] is False
    assert message["unix_socket_only"] is True
    assert message["lua_atomic_revision_fence"] is True
    assert message["concurrent_independent_writer_connections"]==8
    assert message["final_revision"]==13
    assert message["pipelined_two_hash_read"] is True
    assert message["ttl_real_expiry"] is True
    assert message["stream_duplicate_observations_stored"]==2
    assert message["redis_cloud_connected"] is False
    assert message["production_empiredb_touched"] is False
    assert message["money_moved"] is False
    assert message["real_latency_slo_verified"] is False
    assert "V4_LOCAL_REAL_REDIS_ACCEPTANCE_COMPLETE" in result.stdout
