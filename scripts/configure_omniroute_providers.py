#!/usr/bin/env python3
"""Configure OmniRoute provider connections from existing server-side API keys.

Secrets are read from private env files and sent only to loopback OmniRoute.
No credential values are printed.
"""
from __future__ import annotations

import argparse
import http.cookiejar
import json
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request


KEY_TO_PROVIDER = {
    "OPENROUTER_API_KEY": "openrouter",
    "GEMINI_API_KEY": "gemini",
    "GOOGLE_API_KEY": "gemini",
    "NVIDIA_API_KEY": "nvidia",
    "DEEPSEEK_API_KEY": "deepseek",
    "GROQ_API_KEY": "groq",
    "CEREBRAS_API_KEY": "cerebras",
    "SILICONFLOW_API_KEY": "siliconflow",
    "GLM_API_KEY": "glm",
    "ZAI_API_KEY": "zai",
    "HF_TOKEN": "huggingface",
    "MISTRAL_API_KEY": "mistral",
    "TOGETHER_API_KEY": "together",
    "FIREWORKS_API_KEY": "fireworks",
    "COHERE_API_KEY": "cohere",
    "XAI_API_KEY": "xai",
}


def parse_env(path: Path) -> dict[str, str]:
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
        if value:
            values[key] = value
    return values


def json_request(
    opener: urllib.request.OpenerDirector,
    url: str,
    *,
    method: str = "GET",
    body: object | None = None,
    timeout: int = 60,
) -> tuple[int, dict]:
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(
        url,
        data=data,
        headers=headers,
        method=method,
    )
    try:
        with opener.open(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", "replace")
            return response.status, json.loads(raw or "{}")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            payload = json.loads(raw or "{}")
        except json.JSONDecodeError:
            payload = {"error": f"HTTP {exc.code}"}
        return exc.code, payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--home", default="/home/ubuntu")
    parser.add_argument(
        "--provider-env",
        default="/etc/empire_os/omniroute-providers.env",
    )
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:20128",
    )
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    runtime_env = parse_env(Path(args.home) / ".omniroute/.env")
    provider_env = parse_env(Path(args.provider_env))

    password = runtime_env.get("INITIAL_PASSWORD", "")
    if not password:
        print(json.dumps({
            "ok": False,
            "reason": "missing_initial_password",
            "secrets_printed": False,
        }))
        return 2

    cookie_jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(cookie_jar)
    )

    status, login = json_request(
        opener,
        f"{base_url}/api/auth/login",
        method="POST",
        body={"password": password},
        timeout=30,
    )
    if status != 200 or login.get("success") is not True:
        print(json.dumps({
            "ok": False,
            "reason": "management_login_failed",
            "http_status": status,
            "secrets_printed": False,
        }))
        return 3

    status, current = json_request(
        opener,
        f"{base_url}/api/providers?limit=500",
        timeout=30,
    )
    if status != 200:
        print(json.dumps({
            "ok": False,
            "reason": "provider_list_failed",
            "http_status": status,
            "secrets_printed": False,
        }))
        return 4

    connections = current.get("connections")
    if not isinstance(connections, list):
        connections = []

    existing_providers = {
        str(row.get("provider"))
        for row in connections
        if isinstance(row, dict) and row.get("provider")
    }

    selected: dict[str, tuple[str, str]] = {}
    for env_name, provider in KEY_TO_PROVIDER.items():
        secret = provider_env.get(env_name)
        if secret:
            selected.setdefault(provider, (env_name, secret))

    entries = []
    source_by_provider: dict[str, str] = {}
    for provider, (source_env, secret) in sorted(selected.items()):
        if provider in existing_providers:
            continue
        entries.append({
            "provider": provider,
            "name": f"Empire {provider}",
            "apiKey": secret,
            "priority": 1,
        })
        source_by_provider[provider] = source_env

    created: list[dict] = []
    import_errors: list[dict] = []
    if entries:
        status, imported = json_request(
            opener,
            f"{base_url}/api/providers/import",
            method="POST",
            body={"entries": entries, "validateKeys": True},
            timeout=180,
        )
        if status != 200:
            print(json.dumps({
                "ok": False,
                "reason": "provider_import_failed",
                "http_status": status,
                "attempted_providers": sorted(source_by_provider),
                "secrets_printed": False,
            }))
            return 5
        raw_created = imported.get("created")
        raw_errors = imported.get("errors")
        if isinstance(raw_created, list):
            created = [row for row in raw_created if isinstance(row, dict)]
        if isinstance(raw_errors, list):
            import_errors = [row for row in raw_errors if isinstance(row, dict)]

    # Refresh the connection list after import, then sync models for every
    # provider sourced from Empire's existing credentials.
    status, refreshed = json_request(
        opener,
        f"{base_url}/api/providers?limit=500",
        timeout=30,
    )
    refreshed_connections = refreshed.get("connections") if status == 200 else []
    if not isinstance(refreshed_connections, list):
        refreshed_connections = []

    selected_providers = set(selected)
    sync_results = []
    for row in refreshed_connections:
        if not isinstance(row, dict):
            continue
        provider = str(row.get("provider") or "")
        connection_id = str(row.get("id") or "")
        if provider not in selected_providers or not connection_id:
            continue
        encoded = urllib.parse.quote(connection_id, safe="")
        sync_status, _ = json_request(
            opener,
            f"{base_url}/api/providers/{encoded}/sync-models?mode=import",
            method="POST",
            body={},
            timeout=120,
        )
        sync_results.append({
            "provider": provider,
            "ok": 200 <= sync_status < 300,
            "http_status": sync_status,
        })

    safe_errors = []
    for row in import_errors:
        safe_errors.append({
            "provider": row.get("provider"),
            "message": row.get("message"),
        })

    output = {
        "ok": True,
        "discovered_provider_key_count": len(selected),
        "existing_provider_count": len(existing_providers),
        "attempted_provider_count": len(entries),
        "created_providers": sorted(
            str(row.get("provider"))
            for row in created
            if row.get("provider")
        ),
        "import_errors": safe_errors,
        "model_sync": sync_results,
        "secrets_printed": False,
    }
    print(json.dumps(output, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
