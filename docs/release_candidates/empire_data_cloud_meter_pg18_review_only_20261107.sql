-- ISOLATED POSTGRES 18 CANDIDATE COMPILATION ONLY. NO CANONICAL DB RELEASE.
BEGIN;
-- Two isolated NOLOGIN roles. A separate protected activation must provision
-- a secure DB login and verify session_user before enabling this API.
CREATE ROLE empire_data_cloud_api_owner NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
CREATE ROLE empire_data_cloud_meter_login NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
CREATE SCHEMA empire_data_cloud_api;
REVOKE ALL ON SCHEMA empire_data_cloud_api FROM PUBLIC;
CREATE TABLE IF NOT EXISTS empire_data_cloud_api.tenants (
tenant_id text PRIMARY KEY CHECK (length(tenant_id) BETWEEN 1 AND 100),
active boolean NOT NULL DEFAULT false,held boolean NOT NULL DEFAULT true,
monthly_request_cap integer NOT NULL CHECK(monthly_request_cap>=0),
monthly_cost_cap_micros bigint NOT NULL CHECK(monthly_cost_cap_micros>=0),
search_cost_ceiling_micros bigint NOT NULL CHECK(search_cost_ceiling_micros>0),
audit_cost_ceiling_micros bigint NOT NULL CHECK(audit_cost_ceiling_micros>0),
allowed_operations text[] NOT NULL DEFAULT '{}',allowed_hosts text[] NOT NULL DEFAULT '{}');
CREATE TABLE IF NOT EXISTS empire_data_cloud_api.api_keys (
token_sha256 text PRIMARY KEY CHECK(token_sha256~'^[a-f0-9]{64}$'),
tenant_id text NOT NULL REFERENCES empire_data_cloud_api.tenants(tenant_id),
active boolean NOT NULL DEFAULT false,expires_at timestamptz NOT NULL,created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS empire_data_cloud_api.usage_requests (
id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
tenant_id text NOT NULL REFERENCES empire_data_cloud_api.tenants(tenant_id),
month_utc date NOT NULL,operation text NOT NULL CHECK(operation IN ('search','site_audit')),
idempotency_key text NOT NULL CHECK(length(idempotency_key) BETWEEN 8 AND 128),
request_sha256 text NOT NULL CHECK(request_sha256~'^[a-f0-9]{64}$'),
reserved_cost_usd_micros bigint NOT NULL CHECK(reserved_cost_usd_micros>0),
state text NOT NULL DEFAULT 'reserved' CHECK(state IN('reserved','completed','provider_error','cost_integrity_hold')),
unverified_provider_cost_usd_micros bigint CHECK(unverified_provider_cost_usd_micros>=0),
provider_cost_evidence_ref text,created_at timestamptz NOT NULL DEFAULT now(),
updated_at timestamptz NOT NULL DEFAULT now(),UNIQUE(tenant_id,idempotency_key));
CREATE INDEX IF NOT EXISTS idx_data_cloud_usage_month
ON empire_data_cloud_api.usage_requests(tenant_id,month_utc);
REVOKE ALL ON ALL TABLES IN SCHEMA empire_data_cloud_api FROM PUBLIC;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA empire_data_cloud_api FROM PUBLIC;
CREATE OR REPLACE FUNCTION empire_data_cloud_api.authenticate(p_sha256 text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,empire_data_cloud_api AS $$
DECLARE p empire_data_cloud_api.tenants%ROWTYPE;
BEGIN
IF p_sha256 IS NULL OR p_sha256 !~ '^[a-f0-9]{64}$' THEN RAISE EXCEPTION 'invalid_api_key' USING ERRCODE='28000'; END IF;
SELECT t.* INTO p FROM empire_data_cloud_api.tenants t
JOIN empire_data_cloud_api.api_keys k ON k.tenant_id=t.tenant_id
WHERE k.token_sha256=p_sha256 AND k.active AND k.expires_at>now() AND t.active AND NOT t.held;
IF NOT FOUND THEN RAISE EXCEPTION 'invalid_or_held_api_key' USING ERRCODE='28000'; END IF;
RETURN jsonb_build_object('tenant_id',p.tenant_id,'monthly_cap',p.monthly_request_cap,'cost_cap_micros',p.monthly_cost_cap_micros,'search_ceiling_micros',p.search_cost_ceiling_micros,'audit_ceiling_micros',p.audit_cost_ceiling_micros,'operations',p.allowed_operations,'hosts',p.allowed_hosts);
END $$;
CREATE OR REPLACE FUNCTION empire_data_cloud_api.reserve(
p_sha256 text,p_operation text,p_idempotency text,p_request_sha256 text,p_target_host text DEFAULT NULL)
RETURNS bigint LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,empire_data_cloud_api AS $$
DECLARE p empire_data_cloud_api.tenants%ROWTYPE;
DECLARE month_key date:=date_trunc('month',now() AT TIME ZONE 'UTC')::date;
DECLARE used_requests bigint; used_cost bigint; cost_ceiling bigint; new_id bigint;
BEGIN
IF p_sha256 IS NULL OR p_sha256 !~ '^[a-f0-9]{64}$'
OR p_request_sha256 IS NULL OR p_request_sha256 !~ '^[a-f0-9]{64}$'
OR p_idempotency IS NULL OR p_idempotency !~ '^[A-Za-z0-9][A-Za-z0-9._-]{7,127}$'
THEN RAISE EXCEPTION 'invalid_request_identifier' USING ERRCODE='22023'; END IF;
SELECT t.* INTO p FROM empire_data_cloud_api.tenants t JOIN empire_data_cloud_api.api_keys k ON k.tenant_id=t.tenant_id
WHERE k.token_sha256=p_sha256 AND k.active AND k.expires_at>now() AND t.active AND NOT t.held FOR UPDATE OF t;
IF NOT FOUND THEN RAISE EXCEPTION 'invalid_or_held_api_key' USING ERRCODE='28000'; END IF;
IF p_operation IS NULL OR p_operation NOT IN('search','site_audit') OR NOT p_operation=ANY(p.allowed_operations) THEN
RAISE EXCEPTION 'operation_not_entitled' USING ERRCODE='42501'; END IF;
IF p_operation='site_audit' AND (p_target_host IS NULL OR NOT p_target_host=ANY(p.allowed_hosts)) THEN
RAISE EXCEPTION 'host_not_entitled' USING ERRCODE='42501'; END IF;
cost_ceiling:=CASE p_operation WHEN 'search' THEN p.search_cost_ceiling_micros ELSE p.audit_cost_ceiling_micros END;
IF EXISTS(SELECT 1 FROM empire_data_cloud_api.usage_requests u WHERE u.tenant_id=p.tenant_id AND u.idempotency_key=p_idempotency) THEN
RAISE EXCEPTION 'duplicate_request' USING ERRCODE='23505'; END IF;
SELECT count(*),coalesce(sum(u.reserved_cost_usd_micros),0) INTO used_requests,used_cost
FROM empire_data_cloud_api.usage_requests u WHERE u.tenant_id=p.tenant_id AND u.month_utc=month_key;
IF used_requests>=p.monthly_request_cap OR used_cost+cost_ceiling>p.monthly_cost_cap_micros THEN
RAISE EXCEPTION 'cost_or_request_cap_exceeded' USING ERRCODE='P0001'; END IF;
INSERT INTO empire_data_cloud_api.usage_requests(tenant_id,month_utc,operation,idempotency_key,request_sha256,reserved_cost_usd_micros)
VALUES(p.tenant_id,month_key,p_operation,p_idempotency,p_request_sha256,cost_ceiling) RETURNING id INTO new_id;
RETURN new_id; END $$;
CREATE OR REPLACE FUNCTION empire_data_cloud_api.settle(
p_sha256 text,p_reservation_id bigint,p_state text,p_reported_cost_micros bigint DEFAULT NULL,p_evidence_ref text DEFAULT NULL)
RETURNS text LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,empire_data_cloud_api AS $$
DECLARE p empire_data_cloud_api.tenants%ROWTYPE; DECLARE r empire_data_cloud_api.usage_requests%ROWTYPE; DECLARE final_state text:=p_state;
BEGIN
IF p_sha256 IS NULL OR p_sha256 !~ '^[a-f0-9]{64}$' THEN RAISE EXCEPTION 'invalid_api_key' USING ERRCODE='28000'; END IF;
IF p_state IS NULL OR p_state NOT IN('completed','provider_error') THEN RAISE EXCEPTION 'invalid_usage_settlement' USING ERRCODE='22023'; END IF;
IF (p_reported_cost_micros IS NULL)<>(p_evidence_ref IS NULL) OR
(p_reported_cost_micros IS NOT NULL AND (p_reported_cost_micros<0 OR length(p_evidence_ref)>512 OR length(p_evidence_ref)<8)) THEN
RAISE EXCEPTION 'invalid_cost_evidence' USING ERRCODE='22023'; END IF;
SELECT t.* INTO p FROM empire_data_cloud_api.tenants t JOIN empire_data_cloud_api.api_keys k ON k.tenant_id=t.tenant_id
WHERE k.token_sha256=p_sha256 AND k.active AND k.expires_at>now() AND t.active FOR UPDATE OF t;
IF NOT FOUND THEN RAISE EXCEPTION 'invalid_api_key' USING ERRCODE='28000'; END IF;
SELECT * INTO r FROM empire_data_cloud_api.usage_requests u WHERE u.id=p_reservation_id AND u.tenant_id=p.tenant_id FOR UPDATE;
IF NOT FOUND OR r.state<>'reserved' THEN RAISE EXCEPTION 'reservation_not_owned_or_settled' USING ERRCODE='42501'; END IF;
IF p_reported_cost_micros IS NULL OR p_evidence_ref IS NULL OR p_reported_cost_micros>r.reserved_cost_usd_micros THEN
final_state:='cost_integrity_hold'; UPDATE empire_data_cloud_api.tenants SET held=true WHERE tenant_id=p.tenant_id; END IF;
UPDATE empire_data_cloud_api.usage_requests SET state=final_state,
unverified_provider_cost_usd_micros=p_reported_cost_micros,provider_cost_evidence_ref=p_evidence_ref,updated_at=now() WHERE id=r.id;
RETURN final_state; END $$;
CREATE OR REPLACE FUNCTION empire_data_cloud_api.usage_snapshot(p_sha256 text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,empire_data_cloud_api AS $$
DECLARE p empire_data_cloud_api.tenants%ROWTYPE;
DECLARE requests_used bigint; ceiling_used bigint; unknown_cost bigint;
DECLARE month_key date:=date_trunc('month',now() AT TIME ZONE 'UTC')::date;
BEGIN
IF p_sha256 IS NULL OR p_sha256 !~ '^[a-f0-9]{64}$' THEN RAISE EXCEPTION 'invalid_api_key' USING ERRCODE='28000'; END IF;
SELECT t.* INTO p FROM empire_data_cloud_api.tenants t JOIN empire_data_cloud_api.api_keys k ON k.tenant_id=t.tenant_id
WHERE k.token_sha256=p_sha256 AND k.active AND k.expires_at>now() AND t.active;
IF NOT FOUND THEN RAISE EXCEPTION 'invalid_api_key' USING ERRCODE='28000'; END IF;
SELECT count(*),coalesce(sum(u.reserved_cost_usd_micros),0),count(*) FILTER(WHERE u.unverified_provider_cost_usd_micros IS NULL)
INTO requests_used,ceiling_used,unknown_cost FROM empire_data_cloud_api.usage_requests u WHERE u.tenant_id=p.tenant_id AND u.month_utc=month_key;
RETURN jsonb_build_object('window',to_char(month_key,'YYYY-MM'),'request_count',requests_used,'cap',p.monthly_request_cap,
'cost_ceiling_usd_micros',p.monthly_cost_cap_micros,'cost_reserved_usd_micros',ceiling_used,
'unverified_cost_requests',unknown_cost,'verified_actual_cost_usd_micros',NULL,'tenant_cost_hold',p.held,'billing_enabled',false);
END $$;
REVOKE ALL ON FUNCTION empire_data_cloud_api.authenticate(text) FROM PUBLIC;
REVOKE ALL ON FUNCTION empire_data_cloud_api.reserve(text,text,text,text,text) FROM PUBLIC;
REVOKE ALL ON FUNCTION empire_data_cloud_api.settle(text,bigint,text,bigint,text) FROM PUBLIC;
REVOKE ALL ON FUNCTION empire_data_cloud_api.usage_snapshot(text) FROM PUBLIC;
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
COMMIT;