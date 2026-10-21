-- CONSUMER059: ACL seal ONLY for the five freshly created consumer tables.
-- Must run AFTER 057 and BEFORE 058 inside the guarded outer transaction.
-- Preserve all existing database-wide/default privileges, roles and objects.
BEGIN;
SET LOCAL ROLE empiredb_migrator;
SET LOCAL statement_timeout='10s';
SET LOCAL lock_timeout='3s';

DO $guard$
DECLARE
  expected_tables text[] := ARRAY[
    'empire_consumer_subscriptions',
    'empire_consumer_consent_events',
    'empire_consumer_email_suppressions',
    'empire_consumer_one_time_tokens',
    'empire_consumer_delivery_receipts'
  ];
  existing_table_count integer;
BEGIN
  IF current_database() NOT IN ('empiredb','empire_consumer_optin_fixture')
     OR current_user <> 'empiredb_migrator'
  THEN
    RAISE EXCEPTION 'CONSUMER059_WRONG_DATABASE_OR_OPERATOR';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles
                 WHERE rolname='empiredb_app')
     OR NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles
                    WHERE rolname='empiredb_readonly')
  THEN
    RAISE EXCEPTION 'CONSUMER059_EXPECTED_BASELINE_ROLES_ABSENT';
  END IF;
  IF pg_catalog.pg_has_role(
    'empiredb_app','empiredb_migrator','MEMBER')
     OR pg_catalog.pg_has_role(
       'empiredb_readonly','empiredb_migrator','MEMBER')
  THEN
    RAISE EXCEPTION 'CONSUMER059_OWNER_MEMBERSHIP_BOUNDARY_HOLD';
  END IF;
  SELECT count(*) INTO existing_table_count
  FROM pg_catalog.pg_class c
  JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
  WHERE n.nspname='public' AND c.relname=ANY(expected_tables)
    AND c.relkind='r'
    AND c.relowner='empiredb_migrator'::pg_catalog.regrole
    AND c.relrowsecurity AND c.relforcerowsecurity
    AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_policy p
                    WHERE p.polrelid=c.oid);
  IF existing_table_count<>5 THEN
    RAISE EXCEPTION 'CONSUMER059_TABLE_OWNERSHIP_RLS_DRIFT';
  END IF;

  -- Accept ONLY the specific documented unexpected inherited defaults.
  -- Never conceal new unknown role grants or grant options with a broad
  -- REVOKE; unexpected ACL authority must stop the entire transaction.
  IF EXISTS (
    SELECT 1 FROM pg_catalog.pg_class c
    JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
    CROSS JOIN LATERAL pg_catalog.aclexplode(
      COALESCE(c.relacl,pg_catalog.acldefault('r',c.relowner))
    ) acl
    LEFT JOIN pg_catalog.pg_roles r ON r.oid=acl.grantee
    WHERE n.nspname='public'
      AND c.relname=ANY(expected_tables) AND c.relkind='r'
      AND acl.grantee<>c.relowner
      AND (
        acl.is_grantable
        OR r.rolname IS NULL
        OR NOT (
          (r.rolname='empiredb_app'
           AND acl.privilege_type IN ('SELECT','INSERT','UPDATE','DELETE'))
          OR
          (r.rolname='empiredb_readonly'
           AND acl.privilege_type='SELECT')
        )
      )
  ) THEN
    RAISE EXCEPTION 'CONSUMER059_UNEXPECTED_DEFAULT_TABLE_ACL';
  END IF;
END;
$guard$;

-- These REVOKEs apply exclusively to the exact new consumer relations.
-- Never ALTER DEFAULT PRIVILEGES for other EmpireDB owners or modules.
REVOKE ALL PRIVILEGES ON TABLE
  public.empire_consumer_subscriptions,
  public.empire_consumer_consent_events,
  public.empire_consumer_email_suppressions,
  public.empire_consumer_one_time_tokens,
  public.empire_consumer_delivery_receipts
  FROM PUBLIC, empiredb_app, empiredb_readonly;

DO $verify$
DECLARE
  table_name text;
BEGIN
  FOREACH table_name IN ARRAY ARRAY[
    'empire_consumer_subscriptions',
    'empire_consumer_consent_events',
    'empire_consumer_email_suppressions',
    'empire_consumer_one_time_tokens',
    'empire_consumer_delivery_receipts'
  ]
  LOOP
    IF EXISTS (
      SELECT 1 FROM pg_catalog.pg_class c
      CROSS JOIN LATERAL pg_catalog.aclexplode(
        COALESCE(c.relacl,pg_catalog.acldefault('r',c.relowner))
      ) acl
      WHERE c.oid=pg_catalog.to_regclass('public.'||table_name)
        AND acl.grantee<>c.relowner
    ) OR pg_catalog.has_table_privilege(
      'empiredb_app','public.'||table_name,'SELECT'
    ) OR pg_catalog.has_table_privilege(
      'empiredb_readonly','public.'||table_name,'SELECT'
    )
    THEN
      RAISE EXCEPTION 'CONSUMER059_EXACT_TABLE_ACL_SEAL_FAILED';
    END IF;
  END LOOP;
END;
$verify$;
COMMIT;
