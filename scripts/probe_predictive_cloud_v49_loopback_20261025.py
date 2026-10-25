#!/usr/bin/env python3
"""Isolated loopback HTTP acceptance of V4.9 additive Founder API wrapper.

Starts an additional short-lived uvicorn only on 127.0.0.1:3099 for a local
rehearsal. Never restarts or changes the live :8766 systemd service.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

STAGE = Path("/home/ubuntu/empire_releases/predictive_cloud_v49_readonly_20261025")
PYTHON = "/srv/empire_os/.venv/bin/python"
BASE = "http://127.0.0.1:3099"
ENDPOINT = "/v1/predictive-cloud/v4/shadow-readiness"


def get(path: str, *, method: str = "GET") -> tuple[int, dict | str, dict]:
    try:
        with urlopen(Request(BASE + path, method=method), timeout=3) as r:
            raw = r.read(100_000).decode()
            return r.status, json.loads(raw), dict(r.headers.items())
    except HTTPError as exc:
        return exc.code, exc.read(3000).decode(), dict(exc.headers.items())


def main() -> None:
    if not STAGE.is_dir() or not (STAGE / "predictive_cloud_v49_existing_api_overlay_20261025.py").is_file():
        raise RuntimeError("PINNED_V49_RELEASE_STAGE_MISSING")
    with socket.socket() as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", 3099))
        except OSError:
            raise RuntimeError("REHEARSAL_PORT_OCCUPIED") from None

    env = dict(os.environ, PYTHONPATH="/srv/empire_os")
    command = [
        PYTHON, "-B", "-m", "uvicorn", "--app-dir", str(STAGE),
        "predictive_cloud_v49_existing_api_overlay_20261025:app",
        "--host", "127.0.0.1", "--port", "3099", "--no-access-log",
    ]
    with open(os.devnull, "wb") as log:
        proc = subprocess.Popen(
            command, cwd="/srv/empire_os", env=env, stdout=log, stderr=log,
            start_new_session=False,
        )
        try:
            for _ in range(30):
                if proc.poll() is not None:
                    raise RuntimeError("PINNED_APP_DID_NOT_START")
                try:
                    status, content, headers = get("/health")
                    if status == 200:
                        break
                except (URLError, TimeoutError):
                    pass
                time.sleep(.25)
            else:
                raise RuntimeError("PINNED_APP_TIMED_OUT")

            status, health, _ = get("/health")
            assert status == 200 and health["ok"] is True
            status, result, headers = get(ENDPOINT)
            assert status == 200
            assert result["mode"] == "OBSERVE"
            assert result["status"] == "SHADOW_CODE_LOADED_NON_EXECUTING"
            assert result["commercial_prediction_authorized"] is False
            assert result["redis_cloud_producer_activated"] is False
            assert result["production_tenant_source_admitted"] is False
            assert {k.lower(): v for k, v in headers.items()}.get("cache-control") == "no-store, private"
            assert get(ENDPOINT, method="POST")[0] == 405
            assert get("/v1/predictive-cloud/status")[0] == 200
            print(json.dumps({
                "status": "V49_EXISTING_FOUNDER_LOOPBACK_HTTP_PASS",
                "existing_founder_health": True,
                "existing_predictive_cloud_status": True,
                "added_read_only_get": True,
                "writes_refused_405": True,
                "real_customer_data_accessed": False,
                "live_service_8766_changed": False,
                "redis_published": False,
                "database_writes": False,
                "paid_traffic": False,
                "outbound_sent": False,
            }, sort_keys=True))
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)


if __name__ == "__main__":
    main()
