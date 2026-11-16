"""Non-destructive preflight tests for the NVIDIA Docker evaluation manifest."""
from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

from scripts.prepare_nvidia_ontology_docker_eval_20261116 import (
    TARGET, PORT, PROJECT, RESTRICTED_MODEL, _make_compose,
)

pytestmark = pytest.mark.skipif(
    not (TARGET / "compose.yaml").is_file(),
    reason="NVIDIA private evaluation bundle not prepared on this machine",
)


def _contents():
    return yaml.safe_load((TARGET / "compose.yaml").read_text())


def test_bundle_matches_reviewed_source_transform_exactly():
    actual = _contents()
    expected = _make_compose(
        TARGET / "vendor", TARGET / ".env",
        TARGET / "empire_graph.sqlite",
    )
    assert actual == expected


def test_no_public_bind_or_unreviewed_container_names():
    spec = _contents()
    assert spec["name"] == PROJECT
    assert spec["networks"]["sandbox"]["internal"] is True
    assert spec["networks"]["ingress"]["driver"] == "bridge"
    assert spec["networks"]["ingress"]["driver_opts"]["com.docker.network.bridge.host_binding_ipv4"] == "127.0.0.1"
    assert set(spec["services"]) == {
        "postgres", "pgadmin", "auto-ontology", "ingestion-service",
        "auto-ontology-migrate", "frontend-migrate", "auto-ontology-frontend",
    }
    for name, service in spec["services"].items():
        assert "container_name" not in service
        assert service["networks"] == (
            ["sandbox", "ingress"] if name == "auto-ontology-frontend"
            else ["sandbox"]
        )
        assert service["restart"] == "no"
        expected = (
            [f"127.0.0.1:{PORT}:3000"] if name == "auto-ontology-frontend"
            else []
        )
        assert service["ports"] == expected
    assert spec["services"]["pgadmin"]["profiles"] == ["manual"]


def test_only_synthetic_source_mounted_and_private_secrets():
    spec = _contents()
    source = str(TARGET / "empire_graph.sqlite")
    for name in ("auto-ontology", "ingestion-service"):
        bind, = spec["services"][name]["volumes"]
        assert bind["source"] == source
        assert bind["target"] == "/reference/empire_graph.sqlite"
        assert bind["read_only"] is True
    assert (TARGET / "empire_graph.sqlite").stat().st_mode & 0o077 == 0
    assert (TARGET / ".env").stat().st_mode & 0o077 == 0
    assert TARGET.stat().st_mode & 0o077 == 0
    entries = dict(line.split("=", 1) for line in
                   (TARGET / ".env").read_text().splitlines())
    for key in ("POSTGRES_PASSWORD", "AUTO_ONTOLOGY_ADMIN_PASSWORD",
                "PGADMIN_PASSWORD", "AUTH_SECRET"):
        assert len(entries[key]) >= 30
        assert entries[key] not in {"change-me", "autoontologypassword123"}
    models_staged = (TARGET / ".env.disabled-models-20261116").is_file()
    for prefix in ("DEFAULT_MODELS", "REASONING", "NON_REASONING",
                   "EMBED", "RERANK"):
        expected = (
            "http://172.18.0.1:19999/v1"
            if models_staged and prefix != "RERANK"
            else RESTRICTED_MODEL
        )
        assert entries[prefix + "_ENDPOINT"] == expected
        assert entries[prefix + "_API_KEY"] == "offline-model-disabled"
    if models_staged:
        for prefix in ("DEFAULT_MODELS", "REASONING", "NON_REASONING"):
            assert entries[prefix + "_MODEL"] == "openai/qwen2.5-coder:1.5b"
        assert entries["EMBED_MODEL"] == "nomic-embed-text"
        assert entries["RERANK_MODEL"] == "offline-model-disabled"
    assert entries["CONNECTION_STRINGS"] == (
        "sqlite:////reference/empire_graph.sqlite"
    )
    assert "nvapi-" not in (TARGET / ".env").read_text()
