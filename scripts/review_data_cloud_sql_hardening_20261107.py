"""Pin and minimally harden the existing PG18 Data Cloud meter DDL (review-only).

Generates a dedicated proposed migration, not a production execution.
No secret, network, or database access; source hash and edits are exact.
"""
from __future__ import annotations
from pathlib import Path
import hashlib, sys

EXPECTED_ORIGINAL_SHA256 = "f302ad611e93b5f1bdaad40a09cba53c1652c7abe1399a1255ac54d7bdc078e9"
ORIGINAL = Path("/home/ubuntu/empire_releases/data_cloud_pg18_isolated_acceptance_20261107/candidate.sql")
HARDENED = Path("/home/ubuntu/empire_releases/data_cloud_pg18_isolated_acceptance_20261107/candidate_review_hardened.sql")

def replace_exact(text:str,old:str,new:str)->str:
    if text.count(old)!=1:raise ValueError("review baseline drift: "+old[:70])
    return text.replace(old,new,1)

def render(original:str)->str:
    text = replace_exact(original,
        "BEGIN;\nCREATE SCHEMA IF NOT EXISTS empire_data_cloud_api;",
        """BEGIN;
-- Two isolated NOLOGIN roles. A separate protected activation must provision
-- a secure DB login and verify session_user before enabling this API.
CREATE ROLE empire_data_cloud_api_owner NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
CREATE ROLE empire_data_cloud_meter_login NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
CREATE SCHEMA empire_data_cloud_api;""")
    text = replace_exact(text,
        "IF NOT p_operation=ANY(p.allowed_operations) OR p_operation NOT IN('search','site_audit') THEN",
        "IF p_operation IS NULL OR p_operation NOT IN('search','site_audit') OR NOT p_operation=ANY(p.allowed_operations) THEN")
    text = replace_exact(text,
        "IF p_target_host IS NOT NULL AND NOT p_target_host=ANY(p.allowed_hosts) THEN",
        "IF p_operation='site_audit' AND (p_target_host IS NULL OR NOT p_target_host=ANY(p.allowed_hosts)) THEN")
    text = replace_exact(text,
        "IF p_state NOT IN('completed','provider_error') THEN",
        "IF p_state IS NULL OR p_state NOT IN('completed','provider_error') THEN")
    text = replace_exact(text,
        "IF p_reported_cost_micros IS NOT NULL AND p_reported_cost_micros>r.reserved_cost_usd_micros THEN",
        "IF p_reported_cost_micros IS NULL OR p_evidence_ref IS NULL OR p_reported_cost_micros>r.reserved_cost_usd_micros THEN")
    text = replace_exact(text,
        "REVOKE ALL ON FUNCTION empire_data_cloud_api.usage_snapshot(text) FROM PUBLIC;\nCOMMIT;",
        """REVOKE ALL ON FUNCTION empire_data_cloud_api.usage_snapshot(text) FROM PUBLIC;
-- Definer functions must NOT run with bootstrap superuser privileges.
ALTER SCHEMA empire_data_cloud_api OWNER TO empire_data_cloud_api_owner;
ALTER TABLE empire_data_cloud_api.tenants OWNER TO empire_data_cloud_api_owner;
ALTER TABLE empire_data_cloud_api.api_keys OWNER TO empire_data_cloud_api_owner;
ALTER TABLE empire_data_cloud_api.usage_requests OWNER TO empire_data_cloud_api_owner;
ALTER FUNCTION empire_data_cloud_api.authenticate(text) OWNER TO empire_data_cloud_api_owner;
ALTER FUNCTION empire_data_cloud_api.reserve(text,text,text,text,text) OWNER TO empire_data_cloud_api_owner;
ALTER FUNCTION empire_data_cloud_api.settle(text,bigint,text,bigint,text) OWNER TO empire_data_cloud_api_owner;
ALTER FUNCTION empire_data_cloud_api.usage_snapshot(text) OWNER TO empire_data_cloud_api_owner;
REVOKE ALL ON ALL TABLES IN SCHEMA empire_data_cloud_api FROM empire_data_cloud_meter_login;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA empire_data_cloud_api FROM empire_data_cloud_meter_login;
GRANT USAGE ON SCHEMA empire_data_cloud_api TO empire_data_cloud_meter_login;
GRANT EXECUTE ON FUNCTION empire_data_cloud_api.authenticate(text) TO empire_data_cloud_meter_login;
-- Founder usage-only pilot: this runtime role MUST NOT reserve or settle.
-- Future write-capable customer routes require a distinct DBA-reviewed role.
REVOKE ALL ON FUNCTION empire_data_cloud_api.reserve(text,text,text,text,text) FROM empire_data_cloud_meter_login;
REVOKE ALL ON FUNCTION empire_data_cloud_api.settle(text,bigint,text,bigint,text) FROM empire_data_cloud_meter_login;
GRANT EXECUTE ON FUNCTION empire_data_cloud_api.usage_snapshot(text) TO empire_data_cloud_meter_login;
ALTER DEFAULT PRIVILEGES FOR ROLE empire_data_cloud_api_owner
 IN SCHEMA empire_data_cloud_api REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;
COMMIT;""")
    return text

def main():
    b=ORIGINAL.read_bytes()
    if hashlib.sha256(b).hexdigest()!=EXPECTED_ORIGINAL_SHA256:
        raise ValueError("original SQL hash does not match owner receipt")
    candidate=render(b.decode("utf-8"))
    HARDENED.write_text(candidate)
    sha=hashlib.sha256(HARDENED.read_bytes()).hexdigest()
    print(f"REVIEW_SQL_CREATED={HARDENED}")
    print(f"REVIEW_SQL_SHA256={sha}")
    print("PRODUCTION_SQL_APPLIED=false")
    print("PRODUCTION_LOGIN_ENABLED=false")
if __name__=="__main__":main()
