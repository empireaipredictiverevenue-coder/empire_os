"""Guarded NVIDIA model activation script regression (no Docker operations).

The source launcher is tracked in EmpireOS; runtime points to this copy.
Static assertions protect safe defaults, not a claim of successful deployment.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "scripts/activate_nvidia_ontology_local_models_and_capture_20261116.sh"
RUNTIME_LINK = ROOT / "runtime/nvidia_ontology_eval/activate_local_models_and_capture.sh"


def test_local_model_activation_bounds_and_fail_closed():
    content = LAUNCHER.read_text()
    assert 'project=empire-nvidia-ontology-eval' not in content or (
        "empire-nvidia-ontology-eval" in content
    )
    assert "ISOLATED_LOCAL_MODEL_CONFIG_PASS" in content
    assert "CONTAINER_TO_GATEWAY_EMBEDDING_PASS_768_DIM" in content
    assert "CONTAINER_TO_GATEWAY_CHAT_PASS" in content
    assert "timeout 190" in content
    assert "timeout=170" in content
    assert "timeout 65" not in content
    assert 'message.strip().upper().strip(".!")=="OK"' in content
    assert "PRIVATE_MODEL_CANARY_FAILED; containers unchanged" in content
    assert "exit 14" in content
    assert 'up -d --no-deps --no-build --pull never ingestion-service auto-ontology' in content
    assert 'UNTOUCHED_DB_AND_FRONTEND_IDS_CONFIRMED' in content
    assert "LOCAL_MODEL_GATEWAY_UNHEALTHY" in content
    assert "SCOPE_GUARD_NO_DB_OR_FRONTEND" in content
    assert "REASONING_API_KEY" in content
    assert "offline-model-disabled" in content
    assert "sqlite:////reference/empire_graph.sqlite" in content
    assert not any(
        item in content
        for item in (
            "docker system prune", "docker compose down",
            "docker volume rm", "systemctl restart",
            "usermod -aG docker", "chmod 666 /var/run/docker.sock",
        )
    )


def test_runtime_uses_tracked_launcher():
    if RUNTIME_LINK.exists():
        assert RUNTIME_LINK.is_symlink()
        assert RUNTIME_LINK.resolve() == LAUNCHER
