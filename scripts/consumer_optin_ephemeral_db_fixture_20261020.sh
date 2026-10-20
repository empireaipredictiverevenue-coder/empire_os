#!/usr/bin/env bash
set -euo pipefail
if [[ "${PGHOST:-}" != "localhost" ]] || [[ -z "${PGPORT:-}" ]];then echo NOT_EPHEMERAL_PG_VIRTUALENV; exit 3;fi
test "${PGPORT:-5432}" != "5432" || { echo EXPECT_EPHEMERAL_PG_PORT;exit 3; }
printf 'ISOLATED_PG_DSN_HOST=%s port=%s\n' "$PGHOST" "$PGPORT"
psql -X -v ON_ERROR_STOP=1 -d postgres -c "CREATE ROLE empiredb_migrator NOLOGIN NOSUPERUSER NOBYPASSRLS"
createdb -O empiredb_migrator -E UTF8 -T template0 empire_consumer_optin_fixture
psql -X -v ON_ERROR_STOP=1 -d empire_consumer_optin_fixture -f /home/ubuntu/empire_worktrees/consumer_optin_roofing_20261020/migrations/empiredb/057_consumer_roofing_optin_staged_20261020.sql >/dev/null
psql -X -v ON_ERROR_STOP=1 -d empire_consumer_optin_fixture -tA <<'SQL'
SELECT 'EXPECTED_FIVE_TABLES=' || count(*) FROM information_schema.tables
 WHERE table_schema='public' AND table_name LIKE 'empire_consumer_%';
SELECT 'RLS_ENFORCED=' || count(*) FROM pg_class c
 JOIN pg_namespace n ON n.oid=c.relnamespace
 WHERE n.nspname='public' AND c.relname LIKE 'empire_consumer_%'
 AND c.relkind='r' AND c.relrowsecurity AND c.relforcerowsecurity;
SELECT 'PUBLIC_OR_APP_CAN_SELECT=' || count(*) FROM pg_class c
 JOIN pg_namespace n ON n.oid=c.relnamespace
 WHERE n.nspname='public' AND c.relname LIKE 'empire_consumer_%'
 AND c.relkind='r' AND has_table_privilege('public',c.oid,'SELECT');
SELECT 'EVENT_TRIGGER_PRESENT=' || count(*) FROM pg_trigger
 WHERE tgname='empire_consumer_event_immutable' AND NOT tgisinternal;
SELECT 'RLS_POLICIES_CREATED=' || count(*) FROM pg_policies
 WHERE schemaname='public' AND tablename LIKE 'empire_consumer_%';
SQL

psql -X -v ON_ERROR_STOP=1 -d empire_consumer_optin_fixture <<'SQL' >/dev/null
CREATE ROLE consumer_optin_fixture_role NOLOGIN NOSUPERUSER NOBYPASSRLS;
GRANT USAGE ON SCHEMA public TO consumer_optin_fixture_role;
GRANT SELECT,INSERT,UPDATE ON ALL TABLES IN SCHEMA public TO consumer_optin_fixture_role;
DO $$
DECLARE item record;
BEGIN
  FOR item IN SELECT tablename FROM pg_tables WHERE schemaname='public'
    AND tablename LIKE 'empire_consumer_%'
  LOOP
    EXECUTE format('CREATE POLICY fixture_only_access ON public.%I FOR ALL TO consumer_optin_fixture_role USING (true) WITH CHECK (true)', item.tablename);
  END LOOP;
END $$;
SQL
PYTHONPATH=/home/ubuntu/empire_worktrees/consumer_optin_roofing_20261020 /srv/empire_os/.venv/bin/python -B /home/ubuntu/empire_worktrees/consumer_optin_roofing_20261020/scripts/probe_consumer_optin_ephemeral_db_20261020.py

# An admitted temporary test role should still fail if it tries to rewrite
# source consent history. This verifies the trigger, not just its name.
if psql -X -v ON_ERROR_STOP=1 -d empire_consumer_optin_fixture -qAt   -c "UPDATE public.empire_consumer_consent_events SET consent_action='opt_in_requested' WHERE true"   >/dev/null 2>&1; then
  echo "UNEXPECTED_CONSENT_EVENT_MUTABILITY"
  exit 3
fi
echo "APPEND_ONLY_HISTORY_MUTATION_REJECTED=true"
