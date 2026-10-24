"""Real Redis 8.0.5 isolated Unix-socket acceptance for original Predictive Cloud V4.

No Docker, sudo, apt installation, TCP port, Redis Cloud credentials, money,
campaigns, jobs, canonical production EmpireDB connection or live systemd.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
SHELL=ROOT/"scripts/rehearse_predictive_cloud_v4_real_redis8_20261024.sh"
REHEARSAL=ROOT/"scripts/rehearse_predictive_cloud_v4_real_redis_20261024.py"


def test_shell_never_installs_or_starts_host_redis_or_tcp_listener():
    text=SHELL.read_text()
    assert "mktemp -d /tmp/empire-v4-redis-package." in text
    assert "mktemp -d /tmp/empire-v4-redis-run." in text
    assert 'apt download redis-server redis-tools liblzf1' in text
    assert "dpkg-deb -x" in text
    assert "--port 0" in text
    assert '--unixsocket "$run_dir/redis.sock"' in text
    assert "--unixsocketperm 700" in text
    assert '--save "" --appendonly no' in text
    assert "--maxmemory 32mb" in text
    assert "--maxmemory-policy noeviction" in text
    assert "shutdown nosave" in text
    assert 'trap cleanup EXIT' in text
    executable_lines="\n".join(
        line for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )
    assert "systemctl start" not in executable_lines
    assert "apt install" not in executable_lines
    assert "sudo " not in executable_lines


def test_real_redis_fixture_refuses_unverified_socket_without_connecting(tmp_path):
    env=dict(os.environ)
    env["EMPIRE_V4_REDIS_FIXTURE_SOCKET"]=str(tmp_path/"redis.sock")
    output=subprocess.run(
        [sys.executable,"-B",str(REHEARSAL)],
        cwd=ROOT,env=env,capture_output=True,text=True,timeout=5,
    )
    assert output.returncode!=0
    assert "V4_REFUSED_NON_EPHEMERAL_REDIS_UNIX_SOCKET" in output.stderr
    assert "REAL_LOCAL_REDIS8_V4_HOTPATH_PASS" not in output.stdout


@pytest.mark.skipif(
    shutil.which("apt") is None or shutil.which("dpkg-deb") is None,
    reason="unprivileged Ubuntu apt download or dpkg-deb not available",
)
def test_actual_redis8_lua_pipeline_stream_ttl_race_with_temp_cleanup():
    # This deliberately fetches official Ubuntu packages to /tmp. No
    # dependency installation or TCP listener is made. Network is needed.
    run=subprocess.run(
        ["bash",str(SHELL)],cwd=ROOT,
        capture_output=True,text=True,timeout=120,
    )
    assert run.returncode==0,run.stdout[-5000:]+"\n"+run.stderr[-2000:]
    lines=[x for x in run.stdout.splitlines() if x.startswith("{")]
    assert len(lines)==1,run.stdout[-3000:]
    receipt=json.loads(lines[0])
    assert receipt["status"]=="REAL_LOCAL_REDIS8_V4_HOTPATH_PASS"
    assert receipt["redis_version"].startswith("8.")
    assert receipt["unix_socket_only"] is True
    assert receipt["tcp_port"]==0
    assert receipt["persistence_enabled"] is False
    assert receipt["lua_atomic_revision_fence"] is True
    assert receipt["concurrent_independent_writer_connections"]==8
    assert receipt["final_revision"]==13
    assert receipt["pipelined_two_hash_read"] is True
    assert receipt["ttl_real_expiry"] is True
    assert receipt["stream_duplicate_observations_stored"]==2
    assert receipt["redis_cloud_connected"] is False
    assert receipt["production_empiredb_touched"] is False
    assert receipt["money_moved"] is False
    assert receipt["paid_traffic"] is False
    assert receipt["real_latency_slo_verified"] is False
    assert receipt["real_multi_region_semantics_verified"] is False
    assert "V4_REAL_REDIS_EPHEMERAL_RUN_COMPLETE production_touched=false service_installed=false" in run.stdout
