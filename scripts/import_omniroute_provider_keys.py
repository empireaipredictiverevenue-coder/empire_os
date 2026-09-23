#!/usr/bin/env python3
"""Import already-owned LLM API keys into local OmniRoute without printing them."""
from __future__ import annotations

import argparse
import glob
import json
import os
from pathlib import Path
import pwd
import shlex
import subprocess
from typing import Iterable


KEY_TO_PROVIDER = {
    "GEMINI_API_KEY": "gemini",
    "GOOGLE_API_KEY": "gemini",
    "NVIDIA_API_KEY": "nvidia",
    "GROQ_API_KEY": "groq",
    "CEREBRAS_API_KEY": "cerebras",
    "OPENROUTER_API_KEY": "openrouter",
    "DEEPSEEK_API_KEY": "deepseek",
    "SILICONFLOW_API_KEY": "siliconflow",
    "GLM_API_KEY": "glm",
    "ZAI_API_KEY": "glm",
    "HF_TOKEN": "huggingface",
    "MISTRAL_API_KEY": "mistral",
    "TOGETHER_API_KEY": "together",
    "FIREWORKS_API_KEY": "fireworks",
    "COHERE_API_KEY": "cohere",
    "XAI_API_KEY": "xai",
}

SEARCH_FILES = (
    "/etc/empire_os/omniroute-providers.env",
    "/etc/empire_os.env",
    "/etc/empire_os/llm_secrets/*.env",
)


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return values
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if value[:1] in {"'", '"'} and value[-1:] == value[:1]:
            value = value[1:-1]
        if key in KEY_TO_PROVIDER and value:
            values.setdefault(key, value)
    return values


def discover(home: Path) -> dict[str, str]:
    paths: list[Path] = []
    for pattern in SEARCH_FILES:
        paths.extend(Path(p) for p in glob.glob(pattern))
    paths.append(home / ".hermes/.env")

    found: dict[str, str] = {}
    for path in paths:
        found.update(parse_env_file(path))
    return found


def discover_hermes_pool(home: Path) -> dict[str, str]:
    """Read only persisted manual/OAuth API-key values from Hermes auth.json."""
    path = home / ".hermes/auth.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    pools = raw.get("credential_pool")
    if not isinstance(pools, dict):
        return {}

    provider_aliases = {
        "openrouter": "openrouter",
        "nvidia": "nvidia",
        "gemini": "gemini",
        "deepseek": "deepseek",
        "groq": "groq",
        "cerebras": "cerebras",
        "huggingface": "huggingface",
        "fireworks": "fireworks",
    }

    found: dict[str, str] = {}
    for hermes_provider, omni_provider in provider_aliases.items():
        rows = pools.get(hermes_provider)
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            token = str(
                row.get("access_token")
                or row.get("api_key")
                or ""
            ).strip()
            if token:
                found.setdefault(omni_provider, token)
                break
    return found


def run_as_user(user: str, home: Path, args: Iterable[str], env: dict[str, str]):
    uid = pwd.getpwnam(user).pw_uid
    gid = pwd.getpwnam(user).pw_gid

    def demote():
        os.setgid(gid)
        os.setuid(uid)

    merged = {
        "HOME": str(home),
        "USER": user,
        "LOGNAME": user,
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "NVM_DIR": str(home / ".nvm"),
        **env,
    }
    command = (
        'export NVM_DIR="$HOME/.nvm"; '
        '[ ! -s "$NVM_DIR/nvm.sh" ] || . "$NVM_DIR/nvm.sh"; '
        + " ".join(shlex.quote(x) for x in args)
    )
    return subprocess.run(
        ["bash", "-lc", command],
        env=merged,
        text=True,
        capture_output=True,
        timeout=45,
        preexec_fn=demote if os.geteuid() == 0 else None,
    )


def configured_provider_ids(user: str, home: Path) -> set[str]:
    result = run_as_user(
        user,
        home,
        ["omniroute", "providers", "list", "--json"],
        {},
    )
    if result.returncode != 0:
        return set()
    try:
        raw = json.loads(result.stdout)
    except json.JSONDecodeError:
        return set()

    rows = raw
    if isinstance(raw, dict):
        rows = (
            raw.get("connections")
            or raw.get("providers")
            or raw.get("items")
            or []
        )
    if not isinstance(rows, list):
        return set()

    providers: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        value = (
            row.get("provider")
            or row.get("providerId")
            or row.get("provider_id")
        )
        if value:
            providers.add(str(value))
    return providers


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--home", default="/home/ubuntu")
    parser.add_argument("--user", default="ubuntu")
    args = parser.parse_args()
    home = Path(args.home)

    keys = discover(home)
    selected: dict[str, tuple[str, str]] = {}
    for key_name, value in keys.items():
        provider = KEY_TO_PROVIDER[key_name]
        selected.setdefault(provider, (key_name, value))

    for provider, secret in discover_hermes_pool(home).items():
        selected.setdefault(
            provider,
            (f"HERMES_POOL:{provider}", secret),
        )

    existing = configured_provider_ids(args.user, home)
    outcomes = []
    for provider, (source_key, secret) in sorted(selected.items()):
        if provider in existing:
            outcomes.append(
                {
                    "provider": provider,
                    "source_env": source_key,
                    "ok": True,
                    "skipped": "already_configured",
                }
            )
            continue
        env_name = "EMPIRE_OMNIROUTE_IMPORT_KEY"
        result = run_as_user(
            args.user,
            home,
            [
                "omniroute",
                "providers",
                "add",
                provider,
                "--credential-env",
                env_name,
            ],
            {env_name: secret},
        )
        outcomes.append(
            {
                "provider": provider,
                "source_env": source_key,
                "ok": result.returncode == 0,
                "returncode": result.returncode,
            }
        )

    print(
        json.dumps(
            {
                "discovered_provider_count": len(selected),
                "providers": outcomes,
                "secrets_printed": False,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
