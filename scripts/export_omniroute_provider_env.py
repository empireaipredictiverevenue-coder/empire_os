#!/usr/bin/env python3
"""Collect existing authorised provider API keys into OmniRoute's private env.

Never prints secret values. Existing explicit values in the destination win.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
from pathlib import Path
import tempfile


ALLOWED_KEYS = (
    "OPENROUTER_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "NVIDIA_API_KEY",
    "DEEPSEEK_API_KEY",
    "GROQ_API_KEY",
    "CEREBRAS_API_KEY",
    "SILICONFLOW_API_KEY",
    "GLM_API_KEY",
    "ZAI_API_KEY",
    "HF_TOKEN",
    "MISTRAL_API_KEY",
    "TOGETHER_API_KEY",
    "FIREWORKS_API_KEY",
    "COHERE_API_KEY",
    "XAI_API_KEY",
)

ENV_SOURCES = (
    "/etc/empire_os/omniroute-providers.env",
    "/etc/empire_os.env",
    "/etc/empire_os/llm_secrets/*.env",
)


def parse_env(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return out
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if value[:1] in {"'", '"'} and value[-1:] == value[:1]:
            value = value[1:-1]
        if key in ALLOWED_KEYS and value:
            out.setdefault(key, value)
    return out


def hermes_pool(home: Path) -> dict[str, str]:
    path = home / ".hermes/auth.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    pools = raw.get("credential_pool")
    if not isinstance(pools, dict):
        return {}

    mapping = {
        "openrouter": "OPENROUTER_API_KEY",
        "gemini": "GEMINI_API_KEY",
        "nvidia": "NVIDIA_API_KEY",
        "deepseek": "DEEPSEEK_API_KEY",
        "groq": "GROQ_API_KEY",
        "cerebras": "CEREBRAS_API_KEY",
        "huggingface": "HF_TOKEN",
        "fireworks": "FIREWORKS_API_KEY",
    }
    out: dict[str, str] = {}
    for provider, env_name in mapping.items():
        rows = pools.get(provider)
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            value = str(
                row.get("access_token")
                or row.get("api_key")
                or ""
            ).strip()
            if value:
                out.setdefault(env_name, value)
                break
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--home", default="/home/ubuntu")
    parser.add_argument(
        "--output",
        default="/etc/empire_os/omniroute-providers.env",
    )
    args = parser.parse_args()

    output = Path(args.output)
    found: dict[str, str] = {}

    # Existing destination wins over all discoveries.
    found.update(parse_env(output))

    for pattern in ENV_SOURCES:
        for raw_path in glob.glob(pattern):
            for key, value in parse_env(Path(raw_path)).items():
                found.setdefault(key, value)

    for key, value in parse_env(Path(args.home) / ".hermes/.env").items():
        found.setdefault(key, value)

    for key, value in hermes_pool(Path(args.home)).items():
        found.setdefault(key, value)

    output.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix="omniroute-providers.",
        dir=str(output.parent),
        text=True,
    )
    os.close(fd)
    tmp = Path(tmp_name)
    try:
        lines = [
            "# EmpireOS OmniRoute provider credentials.",
            "# Generated from existing authorised server-side credentials.",
            "# Never commit this file.",
        ]
        for key in ALLOWED_KEYS:
            value = found.get(key)
            if value:
                lines.append(f"{key}={value}")
        tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
        os.chmod(tmp, 0o600)
        os.replace(tmp, output)
    finally:
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass

    print(
        json.dumps(
            {
                "output": str(output),
                "provider_key_count": len(found),
                "secrets_printed": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
