"""One-time, reviewable frontend network repair for the isolated NVIDIA evaluation.

The original Compose manifest and its private storage are preserved.
This script makes no Docker calls, service restarts, or prod edits.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path
import yaml

from scripts.prepare_nvidia_ontology_docker_eval_20261116 import (
    TARGET, _make_compose,
)

CURRENT = TARGET / "compose.yaml"
BACKUP = TARGET / "compose.pre-ingress-20261116.yaml"


def apply():
    if not CURRENT.is_file() or not (TARGET / ".env").is_file():
        raise RuntimeError("isolated evaluation manifest not found")
    if BACKUP.exists():
        raise RuntimeError("ingress repair already staged; refuse overwrite")
    current = yaml.safe_load(CURRENT.read_text())
    expected = _make_compose(
        TARGET / "vendor", TARGET / ".env",
        TARGET / "empire_graph.sqlite",
    )
    legacy = yaml.safe_load((TARGET / "vendor/docker-compose.yml").read_text())
    if not isinstance(current, dict) or not isinstance(expected, dict):
        raise RuntimeError("unsupported source manifest")
    if current.get("name") != "empire-nvidia-ontology-eval":
        raise RuntimeError("wrong project")
    if set(current["networks"]) != {"sandbox"} or current["networks"]["sandbox"] != {"internal": True}:
        raise RuntimeError("existing topology drifted; refuse change")
    if current["services"]["auto-ontology-frontend"]["networks"] != ["sandbox"]:
        raise RuntimeError("frontend already has non-legacy network")
    # Verify the proposed change is only a network addition to the frontend.
    old_expected = yaml.safe_load(yaml.safe_dump(expected))
    old_expected["networks"].pop("ingress")
    old_expected["services"]["auto-ontology-frontend"]["networks"] = ["sandbox"]
    if old_expected != current:
        raise RuntimeError("existing manifest differs from known-good template")
    for service in ("postgres", "auto-ontology", "ingestion-service"):
        if current["services"][service] != expected["services"][service]:
            raise RuntimeError("protected service changed")
    shutil.copy2(CURRENT, BACKUP)
    os.chmod(BACKUP, 0o600)
    temp = TARGET / ".compose-ingress-temp.yaml"
    if temp.exists():
        raise RuntimeError("temporary path already present")
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        yaml.safe_dump(expected, f, sort_keys=False)
    os.replace(temp, CURRENT)
    os.chmod(CURRENT, 0o600)
    print("FRONTEND_LOCALHOST_INGRESS_MANIFEST_UPDATED; no containers changed")


if __name__ == "__main__":
    apply()
