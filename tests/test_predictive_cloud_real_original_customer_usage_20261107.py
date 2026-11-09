"""Real original Data Cloud usage endpoint assembled with signed founder gateway.

Offline fake DB is deliberately explicit. Production connections = zero.
"""
from __future__ import annotations
import hashlib, json
from pathlib import Path
from fastapi import FastAPI
from fastapi.testclient import TestClient
from empire_os.predictive_cloud_customer_api.gateway_candidate_entrypoint import create_gateway_candidate_app
from empire_os.predictive_cloud_route_assembly import attach_existing_customer_routes, USAGE_PILOT_REQUIREMENTS
from tests.test_predictive_cloud_route_assembly_20261107 import components, TENANT

class FakeCursor:
    def __init__(self,role="empire_data_cloud_meter_login"):
        self.sql=""
        self.role=role
    def __enter__(self):return self
    def __exit__(self,*_):return False
    def execute(self,sql,params=None):
        self.sql=sql
        self.params=params
        return self
    def fetchone(self):
        if "current_database()" in self.sql:
            return ("empiredb",self.role)
        if "empire_data_cloud_api.authenticate" in self.sql:
            return ({"tenant_id":TENANT,"monthly_cap":5,
                "cost_cap_micros":5000,"search_ceiling_micros":500,
                "audit_ceiling_micros":500,"operations":["site_audit"],
                "hosts":["empire-ai.co.uk"]},)
        if "empire_data_cloud_api.usage_snapshot" in self.sql:
            return ({"window":"2026-11","request_count":0,"cap":5,
                "cost_ceiling_usd_micros":5000,"cost_reserved_usd_micros":0,
                "unverified_cost_requests":0,"verified_actual_cost_usd_micros":None,
                "tenant_cost_hold":False,"billing_enabled":False},)
        raise AssertionError("unexpected db operation "+self.sql)

class FakeConnection:
    def __init__(self,role):self.role=role
    def __enter__(self):return self
    def __exit__(self,*_):return False
    def cursor(self):return FakeCursor(self.role)

def build_host(components, role="empire_data_cloud_meter_login"):
    verifier,state,candidate,evidence,token=components
    source=create_gateway_candidate_app(connect_factory=lambda:FakeConnection(role))
    host=FastAPI()
    @host.get("/existing-owner")
    def untouched():return {"ok":True}
    attached=attach_existing_customer_routes(host,source,verifier,
            release_evidence=lambda:{k:True for k in USAGE_PILOT_REQUIREMENTS},
            usage_only=True)
    assert attached==("/v1/data/usage",)
    return host,state,token

def test_real_original_route_with_two_independent_tokens(components):
    host,state,token=build_host(components)
    api_key="synthetic-first-party-data-key-000001"
    with TestClient(host) as client:
        assert client.get("/existing-owner").json()=={"ok":True}
        assert client.get("/v1/data/usage").status_code==401
        # Signing token alone is insufficient; still requires canonical DB key.
        assert client.get("/v1/data/usage",
            headers={"X-Empire-Data-Session":token()}).status_code==401
        assert client.get("/v1/data/usage",
            headers={"Authorization":"Bearer "+api_key}).status_code==401
        response=client.get("/v1/data/usage",headers={
            "X-Empire-Data-Session":token(),"Authorization":"Bearer "+api_key})
        assert response.status_code==200,response.text
        assert response.json()["request_count"]==0
        assert response.json()["billing_enabled"] is False
        assert response.json()["verified_actual_cost_usd_micros"] is None
        assert response.headers["cache-control"]=="no-store"
        assert client.post("/v1/data/search").status_code==404
        assert client.post("/v1/data/site-audits").status_code==404
        state["entitled"]=False
        denied=client.get("/v1/data/usage",headers={
            "X-Empire-Data-Session":token(),"Authorization":"Bearer "+api_key})
        assert denied.status_code==403

def test_original_route_rejects_wrong_actual_db_login(components):
    host,state,token=build_host(components,role="postgres")
    with TestClient(host) as client:
        response=client.get("/v1/data/usage",headers={
            "X-Empire-Data-Session":token(),
            "Authorization":"Bearer synthetic-first-party-data-key-000001"})
        assert response.status_code==503,response.text
        assert "dedicated_empiredb_meter_role_unverified" in response.text

def test_real_source_conversion_matches_pinned_provenance():
    base=Path(__file__).resolve().parents[1]/"empire_os/predictive_cloud_customer_api"
    manifest=json.loads((base/"SOURCE_PROVENANCE.json").read_text())
    assert manifest["source_archive_sha256"]=="718e752945abd27a20ca28f168f8e20e3b7fe0011151a1a270af76cd0c090ff5"
    assert manifest["only_import_rewrites"] is False
    assert manifest["production_migration"] is False
    assert manifest["public_gateway_activation"] is False
    for name,digest in manifest["converted_sha256"].items():
        assert hashlib.sha256((base/name).read_bytes()).hexdigest()==digest
