-- EmpireDB founder CRM: privileged CATALOG READ ONLY / NO CREDENTIALS.
-- Reports ONLY role/HBA readiness, no contact, customer or credential values.
BEGIN TRANSACTION READ ONLY;
SET LOCAL statement_timeout='5s';
WITH required_roles(rolename) AS (
  VALUES ('empire_crm_auth_login'::text),
         ('empire_crm_membership_login'::text),
         ('empire_crm_tenant_708efd4b53b2'::text)
), applicable_local_hba AS (
 SELECT r.rolename, h.rule_number, h.auth_method,
        h.database, h.user_name
 FROM required_roles r
 JOIN pg_catalog.pg_hba_file_rules h
   ON h.type='local'
  AND (h.database @> ARRAY['empiredb']::text[]
       OR h.database @> ARRAY['all']::text[]
       OR h.database @> ARRAY['sameuser']::text[])
  AND (h.user_name @> ARRAY[r.rolename]::text[]
       OR h.user_name @> ARRAY['all']::text[]
       OR EXISTS (SELECT 1 FROM unnest(h.user_name) u WHERE u LIKE '+%'))
 WHERE h.error IS NULL
), effective_hba AS (
 SELECT DISTINCT ON (rolename) rolename, auth_method, database, user_name
 FROM applicable_local_hba
 ORDER BY rolename, rule_number
), status AS (
 SELECT
   current_database() = 'empiredb' AS canonical_database,
   NOT pg_catalog.pg_is_in_recovery() AS writable_primary,
   NOT EXISTS (
     SELECT 1 FROM pg_catalog.pg_hba_file_rules WHERE error IS NOT NULL
   ) AS hba_configuration_parses,
   (SELECT count(*) FROM effective_hba WHERE auth_method='scram-sha-256'
      AND database=ARRAY['empiredb']::text[] AND user_name=ARRAY[rolename]::text[]
   ) = 3 AS all_three_role_specific_scram_rules_effective,
   (SELECT count(*) FROM pg_catalog.pg_roles
      WHERE rolname IN ('empire_crm_auth_login','empire_crm_membership_login')
        AND NOT rolcanlogin AND NOT rolinherit AND NOT rolsuper
        AND NOT rolbypassrls AND NOT rolcreatedb AND NOT rolcreaterole
   )=2 AS existing_identity_roles_staged,
   NOT EXISTS (
     SELECT 1 FROM pg_catalog.pg_roles
     WHERE rolname='empire_crm_tenant_708efd4b53b2'
   ) AS tenant_reader_role_not_created,
   NOT EXISTS (
     SELECT 1 FROM public.empire_tenant_role_bindings
     WHERE role_name='empire_crm_tenant_708efd4b53b2'
   ) AS tenant_reader_binding_not_created,
   (SELECT count(*) FROM public.empire_crm_tenant_memberships
      WHERE tenant_id='708efd4b-53b2-43d7-961d-1cecab67f17a'::uuid
        AND subject='founder:phil_livesley' AND status='active' AND role='owner'
        AND revoked_at IS NULL AND verified_at <= clock_timestamp()
        AND (valid_until IS NULL OR valid_until > clock_timestamp())
        AND nullif(btrim(evidence_ref),'') IS NOT NULL
   )=1 AS active_founder_owner_verified
)
SELECT pg_catalog.jsonb_pretty(pg_catalog.jsonb_build_object(
 'schema','empire.crm.first_login_auth_transport_preflight.v1',
 'mode','OBSERVE',
 'database_changes',false,
 'customer_contacts_read',false,
 'database_credentials_disclosed',false,
 'canonical_database',canonical_database,
 'writable_primary',writable_primary,
 'hba_configuration_parses',hba_configuration_parses,
 'all_three_role_specific_scram_rules_effective',
   all_three_role_specific_scram_rules_effective,
 'existing_identity_roles_staged',existing_identity_roles_staged,
 'tenant_reader_role_not_created',tenant_reader_role_not_created,
 'tenant_reader_binding_not_created',tenant_reader_binding_not_created,
 'active_founder_owner_verified',active_founder_owner_verified,
 'next_action', CASE
   WHEN NOT canonical_database OR NOT writable_primary
     THEN 'STOP_WRONG_DATABASE'
   WHEN NOT active_founder_owner_verified
     THEN 'STOP_RECONCILE_FOUNDER_MEMBERSHIP'
   WHEN NOT existing_identity_roles_staged
     THEN 'STOP_RECONCILE_IDENTITY_ROLES'
   WHEN NOT tenant_reader_role_not_created OR NOT tenant_reader_binding_not_created
     THEN 'STOP_RECONCILE_EXISTING_READER'
   WHEN NOT hba_configuration_parses
     THEN 'STOP_RECONCILE_PG_HBA'
   WHEN NOT all_three_role_specific_scram_rules_effective
     THEN 'PREPARE_EXACT_LOCAL_SCRAM_AUTH_RULES'
   ELSE 'READY_FOR_APPROVED_THREE_LOGIN_PROVISIONING'
 END
)) AS crm_first_login_transport_preflight
FROM status;
ROLLBACK;
