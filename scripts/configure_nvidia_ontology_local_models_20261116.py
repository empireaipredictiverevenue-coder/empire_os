"""Point only the isolated NVIDIA evaluation at EmpireOS's local Ollama gateway.

One-time preparation only. Never changes containers, production secrets,
database schemas, user roles, networks or public endpoints. Requires later
privileged scoped rollout to apply container environment changes.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from urllib.request import urlopen

ROOT = Path("/srv/empire_os/runtime/nvidia_ontology_eval")
SOURCE = ROOT / ".env"
BACKUP = ROOT / ".env.disabled-models-20261116"
MANIFEST = ROOT / "compose.yaml"
COMPOSE = "/home/ubuntu/.docker/cli-plugins/docker-compose"
OLD = "http://127.0.0.1:19999/v1"
NEW = "http://172.18.0.1:19999/v1"
CHAT = "openai/qwen2.5-coder:1.5b"
EMBED = "nomic-embed-text"

REPLACEMENTS = {
    "DEFAULT_MODELS_ENDPOINT": (OLD, NEW),
    "REASONING_ENDPOINT": (OLD, NEW),
    "NON_REASONING_ENDPOINT": (OLD, NEW),
    "EMBED_ENDPOINT": (OLD, NEW),
    "DEFAULT_MODELS_MODEL": ("offline-model-disabled", CHAT),
    "REASONING_MODEL": ("offline-model-disabled", CHAT),
    "NON_REASONING_MODEL": ("offline-model-disabled", CHAT),
    "EMBED_MODEL": ("offline-model-disabled", EMBED),
}


def prepare() -> dict:
    if not MANIFEST.is_file() or not SOURCE.is_file():
        raise RuntimeError("isolated NVIDIA runtime configuration not found")
    if BACKUP.exists():
        raise RuntimeError("configuration already staged; no overwrite")
    if SOURCE.stat().st_mode & 0o077:
        raise RuntimeError("model configuration is not private")
    with urlopen("http://172.18.0.1:19999/health", timeout=5) as response:
        health = json.load(response)
    if health.get("status") != "ok" or health.get("local_only") is not True:
        raise RuntimeError("local gateway is not healthy")
    original = SOURCE.read_text()
    lines = original.splitlines()
    existing = {}
    for line in lines:
        key, separator, value = line.partition("=")
        if not separator or key in existing:
            raise RuntimeError("duplicate or invalid model config")
        existing[key] = value
    for key, (old, _) in REPLACEMENTS.items():
        if existing.get(key) != old:
            raise RuntimeError(f"unexpected prior value for {key}")
    for key in ("DEFAULT_MODELS_API_KEY", "REASONING_API_KEY",
                "NON_REASONING_API_KEY", "EMBED_API_KEY", "RERANK_API_KEY"):
        if existing.get(key) != "offline-model-disabled":
            raise RuntimeError("nonlocal model credential found; refuse replacement")
    # Reranking is deliberately unsupported; this remains a non-paying hold.
    if existing.get("RERANK_ENDPOINT") != OLD:
        raise RuntimeError("rerank endpoint drift")
    updated = {
        key: REPLACEMENTS[key][1] if key in REPLACEMENTS else value
        for key, value in existing.items()
    }
    shutil.copy2(SOURCE, BACKUP)
    os.chmod(BACKUP, 0o600)
    temp = ROOT / ".env.local-models-staging"
    if temp.exists():
        raise RuntimeError("staging file exists")
    fd = os.open(temp, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w") as handle:
        handle.write("".join(f"{key}={value}\n" for key, value in updated.items()))
    os.replace(temp, SOURCE)
    os.chmod(SOURCE, 0o600)
    p = subprocess.run(
        [COMPOSE, "-f", str(MANIFEST), "--env-file", str(SOURCE), "config", "-q"],
        capture_output=True, text=True, timeout=15,
    )
    if p.returncode:
        # The configuration file is private; keep its old copy for rollback.
        raise RuntimeError("new Compose configuration did not validate")
    return {
        "status": "PRIVATE_LOCAL_MODELS_CONFIGURED_NOT_APPLIED",
        "gateway": NEW,
        "chat_model": CHAT,
        "embedding_model": EMBED,
        "rerank_model_enabled": False,
        "docker_services_restarted": False,
        "secrets_disclosed": False,
        "only_isolated_eval": True,
    }


if __name__ == "__main__":
    print(json.dumps(prepare(), indent=2, sort_keys=True))
