-- CONSUMER058: STAGED ONLY. Apply ONLY after independently approved 057.
-- No LOGIN is created and no user/application inherits this role automatically.
-- DBA must precreate the NOLOGIN NOINHERIT role using their privileged
-- managed procedure. No PUBLIC/web/CRM access, no buyer data export.
BEGIN;
SET LOCAL statement_timeout='10s';
SET LOCAL lock_timeout='3s';

DO $guard$
DECLARE
    n integer;
BEGIN
    IF current_database() NOT IN ('empiredb','empire_consumer_optin_fixture') THEN
      RAISE EXCEPTION 'CONSUMER058_WRONG_DATABASE';
    END IF;
    IF NOT EXISTS (
       SELECT 1 FROM pg_roles
       WHERE rolname='empiredb_migrator' AND NOT rolcanlogin
         AND NOT rolsuper AND NOT rolbypassrls
    ) THEN
      RAISE EXCEPTION 'CONSUMER058_MIGRATOR_NOT_VERIFIED';
    END IF;
    IF NOT EXISTS (
       SELECT 1 FROM pg_roles
       WHERE rolname='empire_consumer_optin_writer'
         AND NOT rolcanlogin AND NOT rolinherit
         AND NOT rolsuper AND NOT rolbypassrls
         AND NOT rolcreatedb AND NOT rolcreaterole AND NOT rolreplication
    ) THEN
      RAISE EXCEPTION 'CONSUMER058_PRIVATE_NOLOGIN_ROLE_NOT_PREPARED';
    END IF;
    SELECT count(*) INTO n
    FROM pg_class c JOIN pg_namespace ns ON ns.oid=c.relnamespace
    WHERE ns.nspname='public'
      AND c.relname IN (
        'empire_consumer_subscriptions',
        'empire_consumer_consent_events',
        'empire_consumer_email_suppressions',
        'empire_consumer_one_time_tokens',
        'empire_consumer_delivery_receipts'
      ) AND c.relkind='r'
      AND c.relrowsecurity AND c.relforcerowsecurity
      AND c.relowner='empiredb_migrator'::regrole;
    IF n <> 5 THEN
      RAISE EXCEPTION 'CONSUMER058_EXACT_FIVE_ENFORCED_TABLES_REQUIRED';
    END IF;
    SELECT count(*) INTO n
    FROM pg_policies WHERE schemaname='public'
      AND tablename IN (
        'empire_consumer_subscriptions',
        'empire_consumer_consent_events',
        'empire_consumer_email_suppressions',
        'empire_consumer_one_time_tokens',
        'empire_consumer_delivery_receipts'
      );
    IF n <> 0 THEN
      RAISE EXCEPTION 'CONSUMER058_EXISTING_POLICIES_REQUIRE_MANUAL_REVIEW';
    END IF;
END;
$guard$;

SET LOCAL ROLE empiredb_migrator;

-- A dedicated narrow-capability service role; production LOGIN identity,
-- membership and key custody require *separate DBA approvals*.
GRANT USAGE ON SCHEMA public TO empire_consumer_optin_writer;
GRANT SELECT, INSERT, UPDATE ON TABLE
  public.empire_consumer_subscriptions
  TO empire_consumer_optin_writer;
GRANT SELECT, INSERT ON TABLE
  public.empire_consumer_consent_events
  TO empire_consumer_optin_writer;
GRANT SELECT, INSERT ON TABLE
  public.empire_consumer_email_suppressions
  TO empire_consumer_optin_writer;
GRANT SELECT, INSERT, UPDATE ON TABLE
  public.empire_consumer_one_time_tokens
  TO empire_consumer_optin_writer;
GRANT SELECT, INSERT ON TABLE
  public.empire_consumer_delivery_receipts
  TO empire_consumer_optin_writer;

CREATE POLICY consumer_writer_subscriptions ON
  public.empire_consumer_subscriptions FOR ALL
  TO empire_consumer_optin_writer
  USING (tenant_scope='empire-ai.co.uk'
     AND purpose='empire_own_brand_homeowner_updates')
  WITH CHECK (tenant_scope='empire-ai.co.uk'
     AND purpose='empire_own_brand_homeowner_updates');

CREATE POLICY consumer_writer_consent_events ON
  public.empire_consumer_consent_events FOR ALL
  TO empire_consumer_optin_writer
  USING (purpose='empire_own_brand_homeowner_updates')
  WITH CHECK (purpose='empire_own_brand_homeowner_updates');

CREATE POLICY consumer_writer_suppressions ON
  public.empire_consumer_email_suppressions FOR ALL
  TO empire_consumer_optin_writer
  USING (purpose='empire_own_brand_homeowner_updates')
  WITH CHECK (purpose='empire_own_brand_homeowner_updates');

-- Tokens and provider receipts reference the single-purpose subscription.
-- No other consumer purpose is permitted in CONSUMER057.
CREATE POLICY consumer_writer_tokens ON
  public.empire_consumer_one_time_tokens FOR ALL
  TO empire_consumer_optin_writer
  USING (EXISTS (
    SELECT 1 FROM public.empire_consumer_subscriptions s
    WHERE s.subscription_id =
      empire_consumer_one_time_tokens.subscription_id
      AND s.tenant_scope='empire-ai.co.uk'
      AND s.purpose='empire_own_brand_homeowner_updates'))
  WITH CHECK (EXISTS (
    SELECT 1 FROM public.empire_consumer_subscriptions s
    WHERE s.subscription_id =
      empire_consumer_one_time_tokens.subscription_id
      AND s.tenant_scope='empire-ai.co.uk'
      AND s.purpose='empire_own_brand_homeowner_updates'));

CREATE POLICY consumer_writer_delivery ON
  public.empire_consumer_delivery_receipts FOR ALL
  TO empire_consumer_optin_writer
  USING (EXISTS (
    SELECT 1 FROM public.empire_consumer_subscriptions s
    WHERE s.subscription_id =
      empire_consumer_delivery_receipts.subscription_id
      AND s.tenant_scope='empire-ai.co.uk'
      AND s.purpose='empire_own_brand_homeowner_updates'))
  WITH CHECK (EXISTS (
    SELECT 1 FROM public.empire_consumer_subscriptions s
    WHERE s.subscription_id =
      empire_consumer_delivery_receipts.subscription_id
      AND s.tenant_scope='empire-ai.co.uk'
      AND s.purpose='empire_own_brand_homeowner_updates'));

-- No public, existing empiredb_app or crm pilot grants. No service login,
-- connection credential, mail key or external caller access is activated.
COMMIT;
