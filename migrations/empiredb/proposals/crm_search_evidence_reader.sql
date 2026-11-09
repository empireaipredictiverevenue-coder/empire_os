-- Candidate reconciled with the founder's 2026-11-09 catalog capture.
-- Run as the existing database administrator; bindings remain empty.
BEGIN;
SET LOCAL lock_timeout = '2s';
SET LOCAL statement_timeout = '10s';
DO $acl_guard$
BEGIN
  IF current_database() NOT IN ('empiredb','crm_search_fixture') THEN
    RAISE EXCEPTION 'unexpected CRM search migration database';
  END IF;
  IF EXISTS (
    SELECT 1 FROM pg_catalog.pg_class c
    WHERE c.oid IN ('public.seo_sites'::regclass,
      'public.seo_backlink_observations'::regclass,
      'public.seo_ai_visibility_observations'::regclass)
      AND (NOT c.relrowsecurity OR
        pg_catalog.has_table_privilege('empiredb_migrator',c.oid,'SELECT'))
  ) THEN
    RAISE EXCEPTION 'CRM search source ACL/RLS baseline drift';
  END IF;

  IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles
    WHERE rolname IN ('empiredb_migrator','empire_revenue_crm_reader','empire_search_reader')
      AND (rolsuper OR rolbypassrls)) THEN
    RAISE EXCEPTION 'CRM search role authority drift';
  END IF;
  IF EXISTS (
    SELECT 1 FROM (VALUES
      ('seo_sites','id','uuid'),('seo_sites','tenant_key','text'),('seo_sites','base_url','text'),
      ('seo_backlink_observations','id','uuid'),('seo_backlink_observations','site_id','uuid'),
      ('seo_backlink_observations','source_url','text'),('seo_backlink_observations','target_url','text'),
      ('seo_backlink_observations','anchor_text','text'),('seo_backlink_observations','rel','text'),
      ('seo_backlink_observations','source','text'),('seo_backlink_observations','provenance','jsonb'),
      ('seo_backlink_observations','observed_at','timestamp with time zone'),
      ('seo_ai_visibility_observations','id','uuid'),('seo_ai_visibility_observations','site_id','uuid'),
      ('seo_ai_visibility_observations','query','text'),('seo_ai_visibility_observations','engine','text'),
      ('seo_ai_visibility_observations','cited_url','text'),('seo_ai_visibility_observations','source_url','text'),
      ('seo_ai_visibility_observations','citation_position','integer'),
      ('seo_ai_visibility_observations','mention_text','text'),('seo_ai_visibility_observations','provenance','jsonb'),
      ('seo_ai_visibility_observations','observed_at','timestamp with time zone')
    ) AS required(table_name,column_name,type_name)
    LEFT JOIN pg_catalog.pg_attribute a
      ON a.attrelid=pg_catalog.to_regclass('public.'||required.table_name)
      AND a.attname=required.column_name AND NOT a.attisdropped
    WHERE a.attnum IS NULL OR pg_catalog.format_type(a.atttypid,a.atttypmod)<>required.type_name
  ) THEN
    RAISE EXCEPTION 'CRM search source schema drift';
  END IF;

  PERFORM pg_catalog.set_config('empire.crm_search_had_site_reference',
    pg_catalog.has_column_privilege('empiredb_migrator',
      'public.seo_sites','id','REFERENCES')::text,true);
END;
$acl_guard$;
GRANT SELECT ON public.seo_sites,public.seo_backlink_observations,
  public.seo_ai_visibility_observations TO empiredb_migrator;
GRANT REFERENCES(id) ON public.seo_sites TO empiredb_migrator;
SET LOCAL ROLE empiredb_migrator;

DO $guard$
BEGIN
  IF current_database() NOT IN ('empiredb', 'crm_search_fixture') THEN
    RAISE EXCEPTION 'unexpected CRM search migration database';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_catalog.pg_proc p
    JOIN pg_catalog.pg_roles r ON r.oid=p.proowner
    WHERE p.oid=pg_catalog.to_regprocedure('public.empire_current_tenant_id()')
      AND p.prosecdef AND p.provolatile='s' AND r.rolname='empiredb_migrator'
  ) OR NOT EXISTS (
    SELECT 1 FROM pg_catalog.pg_proc p
    JOIN pg_catalog.pg_roles r ON r.oid=p.proowner
    WHERE p.oid=pg_catalog.to_regprocedure('public.empire_crm_prospect_authorized(uuid)')
      AND p.prosecdef AND p.provolatile='s' AND r.rolname='empiredb_migrator'
  ) THEN
    RAISE EXCEPTION 'trusted CRM authorization prerequisites missing';
  END IF;
END;
$guard$;

CREATE TABLE public.crm_search_site_bindings (
  tenant_id uuid NOT NULL,
  entity_id uuid NOT NULL REFERENCES public.business_entities(id) ON DELETE RESTRICT,
  site_id uuid NOT NULL REFERENCES public.seo_sites(id) ON DELETE RESTRICT,
  approved_tenant_key text NOT NULL CHECK (length(btrim(approved_tenant_key)) > 0),
  approved_base_url text NOT NULL CHECK (length(btrim(approved_base_url)) > 0),
  evidence_ref text NOT NULL CHECK (length(btrim(evidence_ref)) > 0),
  active boolean NOT NULL DEFAULT false,
  valid_from timestamptz NOT NULL,
  valid_until timestamptz,
  PRIMARY KEY (tenant_id, entity_id, site_id),
  CHECK (valid_until IS NULL OR valid_until > valid_from)
);
REVOKE ALL ON public.crm_search_site_bindings FROM PUBLIC;
REVOKE ALL ON public.crm_search_site_bindings FROM empire_revenue_crm_reader;
COMMENT ON TABLE public.crm_search_site_bindings IS
  'Explicit evidence-backed CRM search scope. Empty on installation; no automatic domain matches.';

RESET ROLE;
DO $reference_restore$
BEGIN
  IF current_setting('empire.crm_search_had_site_reference')='false' THEN
    REVOKE REFERENCES(id) ON public.seo_sites FROM empiredb_migrator;
  END IF;
END;
$reference_restore$;
CREATE POLICY crm_search_bound_sites ON public.seo_sites
  FOR SELECT TO empiredb_migrator
  USING (EXISTS (
    SELECT 1 FROM public.crm_search_site_bindings b
    WHERE b.site_id=seo_sites.id
      AND b.tenant_id=public.empire_current_tenant_id()
      AND b.active
      AND b.valid_from<=CURRENT_TIMESTAMP
      AND (b.valid_until IS NULL OR b.valid_until>CURRENT_TIMESTAMP)
      AND b.approved_tenant_key=seo_sites.tenant_key
      AND b.approved_base_url=seo_sites.base_url
  ));
CREATE POLICY crm_search_bound_backlinks ON public.seo_backlink_observations
  FOR SELECT TO empiredb_migrator
  USING (site_id IN (SELECT s.id FROM public.seo_sites s));
CREATE POLICY crm_search_bound_citations ON public.seo_ai_visibility_observations
  FOR SELECT TO empiredb_migrator
  USING (site_id IN (SELECT s.id FROM public.seo_sites s));
SET LOCAL ROLE empiredb_migrator;
SET LOCAL search_path = '';
DO $policy_guard$
BEGIN
  -- Fail closed on effective policy drift; never misreport filtered rows as no evidence.
  IF (SELECT count(*)=3 AND bool_and(c.relrowsecurity AND
        pg_catalog.has_table_privilege(current_user,c.oid,'SELECT'))
      FROM pg_catalog.pg_class c WHERE c.oid IN (
        'public.seo_sites'::regclass,'public.seo_backlink_observations'::regclass,
        'public.seo_ai_visibility_observations'::regclass)) IS NOT TRUE
    OR (SELECT count(*)=3 AND bool_and(
        p.polcmd='r' AND p.polpermissive AND p.polwithcheck IS NULL
        AND p.polroles=ARRAY[(SELECT oid FROM pg_catalog.pg_roles
                              WHERE rolname='empiredb_migrator')]
        AND CASE
          WHEN p.polrelid='public.seo_sites'::regclass
            THEN p.polname='crm_search_bound_sites'
              AND md5(pg_catalog.pg_get_expr(p.polqual,p.polrelid))='1d13e42ada9728b949845999114ff340'
          WHEN p.polrelid='public.seo_backlink_observations'::regclass
            THEN p.polname='crm_search_bound_backlinks'
              AND md5(pg_catalog.pg_get_expr(p.polqual,p.polrelid))='b3210dbbb972439a79303c19f87d4de7'
          WHEN p.polrelid='public.seo_ai_visibility_observations'::regclass
            THEN p.polname='crm_search_bound_citations'
              AND md5(pg_catalog.pg_get_expr(p.polqual,p.polrelid))='b3210dbbb972439a79303c19f87d4de7'
          ELSE false END)
      FROM pg_catalog.pg_policy p
      WHERE p.polrelid IN ('public.seo_sites'::regclass,
        'public.seo_backlink_observations'::regclass,
        'public.seo_ai_visibility_observations'::regclass)
        AND p.polcmd IN ('r','*')
        AND EXISTS (SELECT 1 FROM unnest(p.polroles) AS role_oid
          WHERE CASE WHEN role_oid=0 THEN true
            ELSE pg_catalog.pg_has_role(current_user,role_oid,'USAGE') END)
      ) IS NOT TRUE THEN
    RAISE EXCEPTION 'CRM search source policy contract drift' USING ERRCODE='42501';
  END IF;

END;
$policy_guard$;

CREATE FUNCTION public.empire_crm_search_evidence(
  p_prospect_id uuid, p_site_id uuid, p_query text, p_engine text,
  p_limit integer DEFAULT 100
) RETURNS TABLE (tenant_id uuid, payload jsonb)
LANGUAGE plpgsql STABLE SECURITY DEFINER
SET search_path = ''
SET row_security = on
AS $reader$
DECLARE
  v_tenant uuid;
  v_entities uuid[];
  v_binding public.crm_search_site_bindings%ROWTYPE;
  v_backlinks jsonb;
  v_citations jsonb;
  v_backlinks_truncated boolean;
  v_citations_truncated boolean;
BEGIN
  IF p_prospect_id IS NULL OR p_site_id IS NULL
     OR p_limit IS NULL OR p_limit < 1 OR p_limit > 100
     OR p_query IS NULL OR length(btrim(p_query))=0 OR length(p_query)>2000
     OR p_engine IS NULL OR length(btrim(p_engine))=0 OR length(p_engine)>100 THEN
    RAISE EXCEPTION 'invalid CRM search selector' USING ERRCODE='22023';
  END IF;

  -- Fail closed on effective policy drift; never misreport filtered rows as no evidence.
  IF (SELECT count(*)=3 AND bool_and(c.relrowsecurity AND
        pg_catalog.has_table_privilege(current_user,c.oid,'SELECT'))
      FROM pg_catalog.pg_class c WHERE c.oid IN (
        'public.seo_sites'::regclass,'public.seo_backlink_observations'::regclass,
        'public.seo_ai_visibility_observations'::regclass)) IS NOT TRUE
    OR (SELECT count(*)=3 AND bool_and(
        p.polcmd='r' AND p.polpermissive AND p.polwithcheck IS NULL
        AND p.polroles=ARRAY[(SELECT oid FROM pg_catalog.pg_roles
                              WHERE rolname='empiredb_migrator')]
        AND CASE
          WHEN p.polrelid='public.seo_sites'::regclass
            THEN p.polname='crm_search_bound_sites'
              AND md5(pg_catalog.pg_get_expr(p.polqual,p.polrelid))='1d13e42ada9728b949845999114ff340'
          WHEN p.polrelid='public.seo_backlink_observations'::regclass
            THEN p.polname='crm_search_bound_backlinks'
              AND md5(pg_catalog.pg_get_expr(p.polqual,p.polrelid))='b3210dbbb972439a79303c19f87d4de7'
          WHEN p.polrelid='public.seo_ai_visibility_observations'::regclass
            THEN p.polname='crm_search_bound_citations'
              AND md5(pg_catalog.pg_get_expr(p.polqual,p.polrelid))='b3210dbbb972439a79303c19f87d4de7'
          ELSE false END)
      FROM pg_catalog.pg_policy p
      WHERE p.polrelid IN ('public.seo_sites'::regclass,
        'public.seo_backlink_observations'::regclass,
        'public.seo_ai_visibility_observations'::regclass)
        AND p.polcmd IN ('r','*')
        AND EXISTS (SELECT 1 FROM unnest(p.polroles) AS role_oid
          WHERE CASE WHEN role_oid=0 THEN true
            ELSE pg_catalog.pg_has_role(current_user,role_oid,'USAGE') END)
      ) IS NOT TRUE THEN
    RAISE EXCEPTION 'CRM search source policy contract drift' USING ERRCODE='42501';
  END IF;

  v_tenant := public.empire_current_tenant_id();
  IF v_tenant IS NULL OR public.empire_crm_prospect_authorized(p_prospect_id) IS NOT TRUE THEN
    RAISE EXCEPTION 'CRM search scope unauthorized' USING ERRCODE='42501';
  END IF;
  SELECT array_agg(l.entity_id) INTO v_entities
  FROM public.prospect_entity_links l
  JOIN public.tenant_business_entity_bindings b ON b.entity_id=l.entity_id
  WHERE l.prospect_id=p_prospect_id AND l.active
    AND l.evidence IS NOT NULL AND l.evidence <> '{}'::jsonb
    AND b.tenant_id=v_tenant AND b.active
    AND b.binding_kind IN ('owned','managed','customer','prospect')
    AND length(btrim(b.evidence_ref))>0
    AND b.valid_from<=CURRENT_TIMESTAMP
    AND (b.valid_until IS NULL OR b.valid_until>CURRENT_TIMESTAMP);
  IF cardinality(v_entities) IS DISTINCT FROM 1 THEN
    RAISE EXCEPTION 'CRM search scope unauthorized' USING ERRCODE='42501';
  END IF;

  SELECT b.* INTO v_binding
  FROM public.crm_search_site_bindings b
  JOIN public.seo_sites s ON s.id=b.site_id
    AND s.tenant_key=b.approved_tenant_key AND s.base_url=b.approved_base_url
  WHERE b.tenant_id=v_tenant AND b.entity_id=v_entities[1]
    AND b.site_id=p_site_id AND b.active
    AND b.valid_from<=CURRENT_TIMESTAMP
    AND (b.valid_until IS NULL OR b.valid_until>CURRENT_TIMESTAMP);
  IF NOT FOUND THEN
    RETURN QUERY SELECT v_tenant, jsonb_build_object('status','NOT_CONNECTED');
    RETURN;
  END IF;

  WITH limited AS (
    SELECT b.id,b.site_id,b.source_url,b.target_url,b.anchor_text,b.rel,
           b.source,b.provenance,b.observed_at
    FROM public.seo_backlink_observations b WHERE b.site_id=p_site_id
    ORDER BY b.observed_at DESC,b.id LIMIT p_limit+1
  ), numbered AS (
    SELECT l.*,row_number() OVER (ORDER BY l.observed_at DESC,l.id) AS rn FROM limited l
  ) SELECT coalesce(jsonb_agg(to_jsonb(n)-'rn' ORDER BY n.rn)
                    FILTER (WHERE n.rn<=p_limit),'[]'::jsonb),count(*)>p_limit
    INTO v_backlinks,v_backlinks_truncated FROM numbered n;

  WITH limited AS (
    SELECT c.id,c.site_id,c.query,c.engine,c.cited_url,c.source_url,
           c.citation_position,c.mention_text,c.provenance,c.observed_at
    FROM public.seo_ai_visibility_observations c
    WHERE c.site_id=p_site_id AND c.query=p_query AND c.engine=p_engine
    ORDER BY c.observed_at DESC,c.id LIMIT p_limit+1
  ), numbered AS (
    SELECT l.*,row_number() OVER (ORDER BY l.observed_at DESC,l.id) AS rn FROM limited l
  ) SELECT coalesce(jsonb_agg(to_jsonb(n)-'rn' ORDER BY n.rn)
                    FILTER (WHERE n.rn<=p_limit),'[]'::jsonb),count(*)>p_limit
    INTO v_citations,v_citations_truncated FROM numbered n;

  RETURN QUERY SELECT v_tenant,jsonb_build_object(
    'status',CASE WHEN jsonb_array_length(v_backlinks)+jsonb_array_length(v_citations)=0
                  THEN 'CONNECTED_NO_OBSERVATIONS' ELSE 'CONNECTED_OBSERVATIONS' END,
    'prospect_id',p_prospect_id,'entity_id',v_entities[1],'site_id',p_site_id,
    'base_url',v_binding.approved_base_url,'binding_evidence_ref',v_binding.evidence_ref,
    'query',p_query,'engine',p_engine,
    'backlinks',v_backlinks,'citations',v_citations,
    'backlinks_truncated',v_backlinks_truncated,'citations_truncated',v_citations_truncated
  );
END;
$reader$;
REVOKE ALL ON FUNCTION public.empire_crm_search_evidence(uuid,uuid,text,text,integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.empire_crm_search_evidence(uuid,uuid,text,text,integer)
  TO empire_revenue_crm_reader;

DO $final_acl_guard$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_catalog.pg_class c,
      LATERAL pg_catalog.aclexplode(coalesce(c.relacl,pg_catalog.acldefault('r',c.relowner))) a
    WHERE c.oid='public.crm_search_site_bindings'::regclass AND a.grantee<>c.relowner
  ) OR EXISTS (
    SELECT 1 FROM pg_catalog.pg_proc p,
      LATERAL pg_catalog.aclexplode(coalesce(p.proacl,pg_catalog.acldefault('f',p.proowner))) a
    WHERE p.oid='public.empire_crm_search_evidence(uuid,uuid,text,text,integer)'::regprocedure
      AND a.grantee NOT IN (p.proowner,
        (SELECT oid FROM pg_catalog.pg_roles WHERE rolname='empire_revenue_crm_reader'))
  ) THEN
    RAISE EXCEPTION 'CRM search unexpected default ACL; no release';
  END IF;
  IF EXISTS (SELECT 1 FROM public.crm_search_site_bindings) THEN
    RAISE EXCEPTION 'CRM search installation must leave bindings empty';
  END IF;
END;
$final_acl_guard$;
COMMIT;
