"""Guard the isolated NVIDIA OAuth resource repair against scope drift.

The browser returned invalid_target: requested 127.0.0.1:33013/mcp,
but the frontend was configured for localhost:33003/mcp.
Do not claim end-to-end OAuth completion without signed-in viewer acceptance.
"""
from __future__ import annotations
import json
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[1]
RUNTIME=ROOT/"runtime/nvidia_ontology_eval"
ENV=RUNTIME/".env"
PREVIOUS=RUNTIME/".env.before-mcp-resource-20261117"
SCRIPT=ROOT/"scripts/activate_nvidia_oauth_resource_frontend_20261117.sh"
STAGE=ROOT/"scripts/stage_nvidia_oauth_resource_fix_20261117.py"


def test_registration_matches_existing_open_code_mcp():
    assert STAGE.is_file()
    script=SCRIPT.read_text()
    assert "ONE_SETTING_OAUTH_RESOURCE_DELTA_VERIFIED" in script
    assert "FRONTEND_PROCESS_OAUTH_RESOURCE_READBACK_PASS" in script
    assert "POSTGRES_BACKEND_INGESTION_IDS_UNCHANGED_PASS" in script
    assert "FRONTEND_OAUTH_RESOURCE_ROLLBACK_ATTEMPTED" in script
    assert "--no-deps --no-build --pull never" in script
    assert "auto-ontology-frontend" in script
    assert "http://127.0.0.1:33013" in script
    assert "http://localhost:33003" in script
    assert "/home/ubuntu/.docker/cli-plugins/docker-compose" in script
    assert "OPENROUTER_API_KEY" not in script
    assert "docker compose down" not in script
    assert "migrate" not in script.lower()
    assert "rm -rf" not in script
    assert "env.before-mcp-resource-20261117" in script


def test_private_env_diff_is_exactly_mcp_resource():
    if not all(p.exists() for p in (ENV,PREVIOUS)):
        pytest.skip("EmpireOS private staged evaluation unavailable")
    assert ENV.stat().st_mode & 0o077 == 0
    assert PREVIOUS.stat().st_mode & 0o077 == 0
    def read(p):
        pairs=[l.split("=",1) for l in p.read_text().splitlines() if "=" in l and not l.startswith("#")]
        assert len(pairs)==len(dict(pairs))
        return dict(pairs)
    old,new=read(PREVIOUS),read(ENV)
    assert old["AUTO_ONTOLOGY_MCP_PUBLIC_URL"]=="http://localhost:33003"
    assert new["AUTO_ONTOLOGY_MCP_PUBLIC_URL"]=="http://127.0.0.1:33013"
    assert {k:v for k,v in old.items() if k!="AUTO_ONTOLOGY_MCP_PUBLIC_URL"}=={
        k:v for k,v in new.items() if k!="AUTO_ONTOLOGY_MCP_PUBLIC_URL"}
    assert new["CONNECTION_STRINGS"]=="sqlite:////reference/empire_graph.sqlite"
    assert new["APP_URL"]=="http://localhost:33000"
    assert new["REASONING_MODEL"]=="openai/nvidia/nemotron-3.5-super-vl:free"
