-- Dedicated runtime capability contract. Applied only by explicit bootstrap.
-- Does not depend on, alter, or apply held migration 018.
DO $$ BEGIN
  IF current_database() <> 'empiredb' THEN
    RAISE EXCEPTION 'EmpireDB required';
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='empire_intelligence_materializer') THEN
    CREATE ROLE empire_intelligence_materializer NOLOGIN NOINHERIT
      NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='empire_intelligence_materializer_login') THEN
    CREATE ROLE empire_intelligence_materializer_login LOGIN NOINHERIT
      NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS CONNECTION LIMIT 3;
  END IF;
END $$;
ALTER ROLE empire_intelligence_materializer NOLOGIN NOINHERIT NOSUPERUSER
  NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
ALTER ROLE empire_intelligence_materializer_login LOGIN NOINHERIT NOSUPERUSER
  NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS CONNECTION LIMIT 3;
GRANT empire_intelligence_materializer TO empire_intelligence_materializer_login;
REVOKE empire_intelligence_materializer FROM empiredb_app;
ALTER ROLE empire_intelligence_materializer_login SET statement_timeout='15s';
ALTER ROLE empire_intelligence_materializer_login SET idle_in_transaction_session_timeout='30s';
GRANT CONNECT ON DATABASE empiredb TO empire_intelligence_materializer_login;
GRANT USAGE ON SCHEMA public TO empire_intelligence_materializer;

-- Fail closed on pre-existing roles with unexpected memberships or ownership.
DO $$ BEGIN
  IF EXISTS (
    SELECT FROM pg_auth_members m JOIN pg_roles r ON r.oid=m.member
    JOIN pg_roles parent ON parent.oid=m.roleid
    WHERE r.rolname IN ('empire_intelligence_materializer','empire_intelligence_materializer_login')
      AND NOT (r.rolname='empire_intelligence_materializer_login'
               AND parent.rolname='empire_intelligence_materializer')
  ) OR EXISTS (
    SELECT FROM pg_class c JOIN pg_roles r ON r.oid=c.relowner
    WHERE r.rolname IN ('empire_intelligence_materializer','empire_intelligence_materializer_login')
  ) THEN RAISE EXCEPTION 'unexpected materializer authority'; END IF;
END $$;
REVOKE ALL ON ALL TABLES IN SCHEMA public
  FROM empire_intelligence_materializer, empire_intelligence_materializer_login;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public
  FROM empire_intelligence_materializer, empire_intelligence_materializer_login;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public
  FROM empire_intelligence_materializer, empire_intelligence_materializer_login;
GRANT SELECT ON public.prospects, public.prospect_entity_links,
  public.prospect_qualifications, public.business_entities, public.intelligence_sources,
  public.intelligence_facts, public.intelligence_scores, public.intelligence_signals
  TO empire_intelligence_materializer;
GRANT INSERT ON public.intelligence_facts, public.intelligence_scores,
  public.intelligence_signals TO empire_intelligence_materializer;

CREATE UNIQUE INDEX IF NOT EXISTS uq_intelligence_facts_evidence_hash
  ON public.intelligence_facts(evidence_hash) WHERE evidence_hash IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_intelligence_scores_materialized
  ON public.intelligence_scores(entity_type,entity_id,score_type,model_key,scored_at);

-- Enforce the same append contract even on EmpireDB tables without RLS.
-- SECURITY INVOKER preserves current_user; no new definer authority is created.
CREATE OR REPLACE FUNCTION public.guard_intelligence_materializer_insert()
RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog,public AS $$
DECLARE valid boolean := false;
BEGIN
  IF current_user <> 'empire_intelligence_materializer' THEN RETURN NEW; END IF;
  IF TG_TABLE_NAME='intelligence_facts' THEN
    valid := NEW.entity_type='company' AND NEW.evidence_hash IS NOT NULL
      AND NEW.source_id=(SELECT id FROM public.intelligence_sources
                         WHERE source_key='empire.prospect.canonical.v1');
  ELSIF TG_TABLE_NAME='intelligence_scores' THEN
    valid := NEW.entity_type='company' AND NEW.score_type='lead_qualification'
      AND NEW.model_key IN ('empire_os.lead_scoring:v1','empire_os.lead_scoring:v2');
  ELSIF TG_TABLE_NAME='intelligence_signals' THEN
    valid := EXISTS (
      SELECT FROM public.intelligence_sources s
      JOIN (VALUES
        ('competitor_audience_evidence','competitive_intelligence','empire.competitor_audience.public.v1'),
        ('competitor_ecosystem_evidence','competitive_intelligence','empire.competitor_ecosystem.public.v1'),
        ('competitor_public_review_presence','competitive_intelligence','empire.competitor_public_reviews.public.v1'),
        ('competitor_search_presence','search_intelligence','empire.competitor_search_presence.public.v1'),
        ('competitor_public_activity','competitive_intelligence','empire.competitor_public_activity.public.v1')
      ) AS allowed(kind,domain,source_key) ON s.source_key=allowed.source_key
      WHERE s.id=NEW.source_id AND NEW.signal_type=allowed.kind
        AND NEW.signal_domain=allowed.domain
    ) AND NEW.payload->>'outreach_enabled'='false'
      AND NEW.payload->>'buyer_intent'='false'
      AND NEW.payload->>'commercial_intent'='false'
      AND NEW.payload->>'prospect_created'='false';
    IF NEW.signal_type='competitor_search_presence' THEN
      valid := valid AND NEW.payload->>'market_share_inferred'='false'
        AND NEW.payload->>'demand_inferred'='false';
    END IF;
  END IF;
  IF valid IS DISTINCT FROM true THEN
    RAISE EXCEPTION 'materializer append contract rejected';
  END IF;
  RETURN NEW;
END $$;
REVOKE ALL ON FUNCTION public.guard_intelligence_materializer_insert() FROM PUBLIC;

DO $$ DECLARE t text; BEGIN
  FOREACH t IN ARRAY ARRAY['intelligence_facts','intelligence_scores','intelligence_signals'] LOOP
    EXECUTE format('DROP TRIGGER IF EXISTS intelligence_materializer_insert_guard ON public.%I',t);
    EXECUTE format('CREATE TRIGGER intelligence_materializer_insert_guard BEFORE INSERT ON public.%I FOR EACH ROW EXECUTE FUNCTION public.guard_intelligence_materializer_insert()',t);
  END LOOP;
  -- Policies only affect tables already governed by RLS. No global RLS switch.
  FOREACH t IN ARRAY ARRAY['prospects','prospect_entity_links','prospect_qualifications',
      'business_entities','intelligence_sources','intelligence_facts','intelligence_scores','intelligence_signals'] LOOP
    EXECUTE format('DROP POLICY IF EXISTS empiredb_materializer_read ON public.%I',t);
    EXECUTE format('CREATE POLICY empiredb_materializer_read ON public.%I FOR SELECT TO empire_intelligence_materializer USING (true)',t);
  END LOOP;
  FOREACH t IN ARRAY ARRAY['intelligence_facts','intelligence_scores','intelligence_signals'] LOOP
    EXECUTE format('DROP POLICY IF EXISTS empiredb_materializer_append ON public.%I',t);
    EXECUTE format('CREATE POLICY empiredb_materializer_append ON public.%I FOR INSERT TO empire_intelligence_materializer WITH CHECK (true)',t);
  END LOOP;
END $$;

-- Existing sources must already be canonical: never invent observation records.
-- Grant only already-installed reader functions, never commercial mutation RPCs.
DO $$ DECLARE f record; BEGIN
  FOR f IN SELECT p.oid::regprocedure AS signature FROM pg_proc p
    JOIN pg_namespace n ON n.oid=p.pronamespace
    WHERE n.nspname='public' AND p.proname IN (
      'get_founder_commercial_funnel','get_commercial_product_catalog',
      'get_market_sweep_revenue_gps','get_revenue_pulse_window'
    ) LOOP
    EXECUTE format('GRANT EXECUTE ON FUNCTION %s TO empire_intelligence_materializer',f.signature);
  END LOOP;
END $$;

-- A dedicated login cannot be least privilege if PUBLIC bypasses its grants.
-- Refuse provisioning rather than changing unrelated production privileges.
DO $$ BEGIN
  IF EXISTS (
    SELECT FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace,
      LATERAL aclexplode(COALESCE(c.relacl, acldefault('r',c.relowner))) a
    WHERE n.nspname='public' AND a.grantee=0
      -- Extension membership, not object names or ordinary dependencies.
      AND NOT EXISTS (
        SELECT FROM pg_depend d JOIN pg_extension e ON e.oid=d.refobjid
        WHERE d.classid='pg_class'::regclass AND d.objid=c.oid
          AND d.objsubid=0 AND d.refclassid='pg_extension'::regclass
          AND d.refobjsubid=0 AND d.deptype='e'
      )
  ) OR EXISTS (
    SELECT FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace,
      LATERAL aclexplode(COALESCE(p.proacl, acldefault('f',p.proowner))) a
    WHERE n.nspname='public' AND p.prosecdef AND a.grantee=0
      AND a.privilege_type='EXECUTE'
      AND p.proname NOT IN ('get_founder_commercial_funnel',
        'get_commercial_product_catalog','get_market_sweep_revenue_gps','get_revenue_pulse_window')
  ) THEN RAISE EXCEPTION 'PUBLIC authority audit required before materializer provisioning'; END IF;
END $$;
