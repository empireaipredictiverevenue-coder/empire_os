"""OpenCode Zen model catalogue discovery for Empire OS."""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path


SECRET_FILE = Path("/etc/empire_os/llm_secrets/opencode_zen.env")
CACHE_FILE = Path(
    os.environ.get(
        "EMPIRE_ZEN_CATALOG_CACHE",
        "/srv/empire_os/runtime/llm/opencode_zen_models.json",
    )
)
BASE_URL = os.environ.get(
    "OPENCODE_ZEN_BASE",
    "https://opencode.ai/zen/v1",
).rstrip("/")


def load_key() -> str:
    try:
        for line in SECRET_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("OPENCODE_ZEN_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return os.environ.get("OPENCODE_ZEN_API_KEY", "")


def discover(timeout: int = 10) -> list[dict]:
    key = load_key()
    if not key:
        raise RuntimeError("opencode_zen_key_missing")

    req = urllib.request.Request(
        f"{BASE_URL}/models",
        headers={
            "Authorization": f"Bearer {key}",
            "Accept": "application/json",
            "User-Agent": "EmpireOS/2.0",
        },
    )

    with urllib.request.urlopen(req, timeout=timeout) as response:
        data = json.loads(response.read().decode())

    models = []
    for item in data.get("data", []):
        model_id = str(item.get("id") or "").strip()
        if not model_id:
            continue

        lower = model_id.lower()

        # Provider catalogue evidence is authoritative for availability.
        # Pricing/capabilities may be absent, so unknown is preserved.
        models.append(
            {
                "model_id": f"zen:{model_id}",
                "provider": "opencode",
                "model": model_id,
                "available": True,
                "free": lower.endswith("-free"),
                "reasoning": any(
                    token in lower
                    for token in (
                        "opus",
                        "pro",
                        "reason",
                        "thinking",
                        "gpt-5.6",
                        "gpt-5.5",
                        "gpt-5.4",
                        "deepseek-v4-pro",
                        "glm-5.3",
                        "kimi-k3",
                    )
                ),
                "capabilities": [
                    "general",
                ],
                "pricing_known": False,
                "discovered_at": time.time(),
            }
        )

    return models


def save(models: list[dict]) -> None:
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = CACHE_FILE.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(
            {
                "schema_version": "zen_catalog.v1",
                "fetched_at": time.time(),
                "models": models,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    tmp.replace(CACHE_FILE)


if __name__ == "__main__":
    models = discover()
    save(models)
    print("ZEN CATALOG: OK")
    print("MODEL COUNT:", len(models))
    print("FREE COUNT:", sum(1 for m in models if m["free"]))
    print("CACHE:", CACHE_FILE)
    for m in models[:20]:
        print(m["model"])
