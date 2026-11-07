"""End-to-end original founder-only usage handler against disposable PostgreSQL 18.

Execution requires EMPIRE_CLOUD_TEST_PG_SOCK pointing to the fixed private
disposable socket root, port 55442. No production access or network calls.
"""
from __future__ import annotations
import hashlib
import os
from pathlib import Path

import psycopg
from fastapi import FastAPI
from fastapi.testclient import TestClient
from tests.test_predictive_cloud_route_assembly_20261107 import components, TENANT
from empire_os.predictive_cloud_customer_api.gateway_candidate_entrypoint import (
    create_gateway_candidate_app,
)
from empire_os.predictive_cloud_route_assembly import (
    attach_existing_customer_routes, USAGE_PILOT_REQUIREMENTS,
)

ROOT = Path("/home/ubuntu/empire_releases/data_cloud_pg18_real_handler_test_20261107")
PORT = 55442


def run() -> None:
    value = os.environ.get("EMPIRE_CLOUD_TEST_PG_SOCK", "")
    if value != str(ROOT) or not ROOT.is_dir() or ROOT.is_symlink():
        raise RuntimeError("private_disposable_pg18_socket_required")
    if os.environ.get("EMPIRE_CLOUD_TEST_PG_PORT") != str(PORT):
        raise RuntimeError("private_disposable_pg18_port_required")

    def connect_as(role: str):
        return psycopg.connect(
            dbname="empiredb", user=role, host=str(ROOT), port=PORT,
            connect_timeout=4,
        )

    api_key = "synthetic-local-only-test-api-key-000000001"
    with connect_as("postgres") as db:
        data_dir = db.execute("SELECT current_setting('data_directory')").fetchone()[0]
        address = db.execute("SELECT inet_server_addr()").fetchone()[0]
        encoding = db.execute("SHOW server_encoding").fetchone()[0]
        if isinstance(data_dir, bytes):
            data_dir = data_dir.decode("utf8")
        assert Path(data_dir).resolve() == ROOT.resolve() and address is None
        assert encoding == "UTF8", "isolation_must_match_production_encoding"
        db.execute(
            """INSERT INTO empire_data_cloud_api.tenants
            (tenant_id,active,held,monthly_request_cap,monthly_cost_cap_micros,
             search_cost_ceiling_micros,audit_cost_ceiling_micros,allowed_operations,allowed_hosts)
            VALUES (%s,true,false,5,5000,500,500,ARRAY[]::text[],ARRAY[]::text[])""",
            (TENANT,),
        )
        db.execute(
            """INSERT INTO empire_data_cloud_api.api_keys
            (token_sha256,tenant_id,active,expires_at)
            VALUES(%s,%s,true,now()+interval '1 hour')""",
            (hashlib.sha256(api_key.encode()).hexdigest(), TENANT),
        )
        # Disposable server only; no production credentials created.
        db.execute("ALTER ROLE empire_data_cloud_meter_login LOGIN")

    def connect_meter():
        return connect_as("empire_data_cloud_meter_login")

    verifier, state, _, _, data_token = components.__wrapped__()
    host = FastAPI()

    @host.get("/existing-owner")
    def existing_owner():
        return {"unchanged": True}

    candidate = create_gateway_candidate_app(connect_factory=connect_meter)
    mounted = attach_existing_customer_routes(
        host, candidate, verifier, usage_only=True,
        release_evidence=lambda: {k: True for k in USAGE_PILOT_REQUIREMENTS},
    )
    assert mounted == ("/v1/data/usage",), mounted
    headers = {
        "X-Empire-Data-Session": data_token(),
        "Authorization": "Bearer " + api_key,
    }
    with TestClient(host) as client:
        assert client.get("/existing-owner").json() == {"unchanged": True}
        assert client.get("/v1/data/usage").status_code == 401
        assert client.get(
            "/v1/data/usage",
            headers={"X-Empire-Data-Session": data_token()},
        ).status_code == 401
        assert client.get(
            "/v1/data/usage",
            headers={"Authorization": "Bearer " + api_key},
        ).status_code == 401
        response = client.get("/v1/data/usage", headers=headers)
        assert response.status_code == 200, (response.status_code, response.json())
        payload = response.json()
        assert payload["request_count"] == 0
        assert payload["billing_enabled"] is False
        assert payload["verified_actual_cost_usd_micros"] is None
        assert response.headers["cache-control"] == "no-store"
        bad = dict(headers)
        bad["Authorization"] = "Bearer invalid-local-test-credential"
        assert client.get("/v1/data/usage", headers=bad).status_code == 401
        assert client.post("/v1/data/search").status_code == 404
        assert client.post("/v1/data/site-audits").status_code == 404
        state["entitled"] = False
        assert client.get("/v1/data/usage", headers=headers).status_code == 403

    with connect_meter() as db:
        try:
            db.execute(
                "SELECT empire_data_cloud_api.reserve(%s,%s,%s,%s,%s)",
                ("x" * 64, "search", "synthetic-test-0001", "y" * 64, None),
            )
        except psycopg.errors.InsufficientPrivilege:
            pass
        else:
            raise AssertionError("write_function_became_accessible")

    print("ORIGINAL_CUSTOMER_HANDLER_REAL_PG18_ISOLATED_HTTP_200=true")
    print("DOUBLE_AUTH_401_AND_REVOKED_403=true")
    print("NO_SEARCH_OR_AUDITS=true,WRITE_FUNCTION_DENIED=true")
    print("SOURCE_DB=DISPOSABLE_UNIX_SOCKET_ONLY,PRODUCTION_WRITES=0")


if __name__ == "__main__":
    run()
