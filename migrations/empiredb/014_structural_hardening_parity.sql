-- Empire Data Cloud — final structural hardening parity
-- Migration: empiredb/014_structural_hardening_parity
-- Source: canonical Supabase semantic schema + verified EmpireDB shadow copy.
-- Safety: schema/security only. No data copy, delete, truncate, outbound, or cutover.

SET ROLE empiredb_migrator;

-- Exact numeric precision/scale parity. The shadow data was already verified
-- byte-for-identity at the primary-key level and originated from these source
-- types, so these casts tighten metadata without inventing values.
ALTER TABLE public.buyer_candidate_reviews
    ALTER COLUMN company_score TYPE NUMERIC(6,2),
    ALTER COLUMN decision_score TYPE NUMERIC(5,4);

ALTER TABLE public.buyers
    ALTER COLUMN monthly_retainer TYPE NUMERIC(12,2),
    ALTER COLUMN per_call_fee TYPE NUMERIC(12,2),
    ALTER COLUMN per_lead_rate TYPE NUMERIC(6,2),
    ALTER COLUMN per_minute_rate TYPE NUMERIC(6,2),
    ALTER COLUMN per_schedule_rate TYPE NUMERIC(6,2);

ALTER TABLE public.crypto_payment_requests
    ALTER COLUMN amount_usdc TYPE NUMERIC(12,2),
    ALTER COLUMN paid_amount_usdc TYPE NUMERIC(12,2);

ALTER TABLE public.intelligence_contact_points
    ALTER COLUMN confidence TYPE NUMERIC(5,4);

ALTER TABLE public.intelligence_facts
    ALTER COLUMN confidence TYPE NUMERIC(5,4);

ALTER TABLE public.intelligence_people
    ALTER COLUMN identity_confidence TYPE NUMERIC(5,4);

ALTER TABLE public.intelligence_scores
    ALTER COLUMN confidence TYPE NUMERIC(5,4),
    ALTER COLUMN score TYPE NUMERIC(9,4);

ALTER TABLE public.intelligence_signals
    ALTER COLUMN confidence TYPE NUMERIC(5,4),
    ALTER COLUMN strength TYPE NUMERIC(5,4);

ALTER TABLE public.intelligence_sources
    ALTER COLUMN authority_score TYPE NUMERIC(5,4);

ALTER TABLE public.outbound_replies
    ALTER COLUMN confidence TYPE NUMERIC(5,4);

ALTER TABLE public.prospect_qualifications
    ALTER COLUMN business_presence_score TYPE NUMERIC(5,1),
    ALTER COLUMN data_completeness_score TYPE NUMERIC(5,1),
    ALTER COLUMN engagement_potential_score TYPE NUMERIC(5,1),
    ALTER COLUMN enrichment_quality_score TYPE NUMERIC(5,1),
    ALTER COLUMN evidence_confidence TYPE NUMERIC(5,4),
    ALTER COLUMN market_fit_score TYPE NUMERIC(5,1),
    ALTER COLUMN score TYPE NUMERIC(5,1);

-- Missing canonical indexes.
CREATE INDEX IF NOT EXISTS idx_business_entities_resolution_state
    ON public.business_entities (resolution_state);

CREATE INDEX IF NOT EXISTS idx_business_entity_conflicts_prospect
    ON public.business_entity_conflicts (prospect_id);

CREATE INDEX IF NOT EXISTS idx_commercial_events_job_event_created
    ON public.commercial_events (job_id, event_type, created_at);

-- RLS parity for the 37 tables that were not already hardened in migrations
-- 003/006. Policies are created only for operations the role ALREADY has via
-- SQL grants. RLS therefore cannot widen privileges; it only preserves the
-- existing capability model once row security is enabled.
DO $$
DECLARE
    v_table TEXT;
    v_tables CONSTANT TEXT[] := ARRAY[
        'astra_observer_tokens',
        'business_entities',
        'business_entity_conflicts',
        'buyer_candidate_review_events',
        'buyer_candidate_reviews',
        'buyer_scout_candidates',
        'buyer_subscriptions',
        'buyers',
        'closer_cases',
        'commercial_events',
        'commercial_evidence_registry',
        'commercial_product_catalog_events',
        'commercial_product_versions',
        'commercial_products',
        'crypto_payment_requests',
        'enriched_leads',
        'fulfilment_orders',
        'gtm_experiments',
        'gtm_jobs',
        'gtm_opportunities',
        'intelligence_contact_points',
        'intelligence_facts',
        'intelligence_outcomes',
        'intelligence_people',
        'intelligence_scores',
        'intelligence_segments',
        'intelligence_signals',
        'intelligence_sources',
        'outbound_events',
        'outbound_intents',
        'outbound_replies',
        'outbound_suppressions',
        'outreach_log',
        'prospect_entity_links',
        'prospect_qualifications',
        'prospects',
        'strike_packs'
    ];
    v_rel TEXT;
    v_policy TEXT;
BEGIN
    FOREACH v_table IN ARRAY v_tables LOOP
        v_rel := format('public.%I', v_table);

        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', v_table);

        IF has_table_privilege('empiredb_app', v_rel, 'SELECT') THEN
            v_policy := v_table || '_app_select';
            EXECUTE format('DROP POLICY IF EXISTS %I ON public.%I', v_policy, v_table);
            EXECUTE format(
                'CREATE POLICY %I ON public.%I FOR SELECT TO empiredb_app USING (true)',
                v_policy, v_table
            );
        END IF;

        IF has_table_privilege('empiredb_app', v_rel, 'INSERT') THEN
            v_policy := v_table || '_app_insert';
            EXECUTE format('DROP POLICY IF EXISTS %I ON public.%I', v_policy, v_table);
            EXECUTE format(
                'CREATE POLICY %I ON public.%I FOR INSERT TO empiredb_app WITH CHECK (true)',
                v_policy, v_table
            );
        END IF;

        IF has_table_privilege('empiredb_app', v_rel, 'UPDATE') THEN
            v_policy := v_table || '_app_update';
            EXECUTE format('DROP POLICY IF EXISTS %I ON public.%I', v_policy, v_table);
            EXECUTE format(
                'CREATE POLICY %I ON public.%I FOR UPDATE TO empiredb_app USING (true) WITH CHECK (true)',
                v_policy, v_table
            );
        END IF;

        IF has_table_privilege('empiredb_app', v_rel, 'DELETE') THEN
            v_policy := v_table || '_app_delete';
            EXECUTE format('DROP POLICY IF EXISTS %I ON public.%I', v_policy, v_table);
            EXECUTE format(
                'CREATE POLICY %I ON public.%I FOR DELETE TO empiredb_app USING (true)',
                v_policy, v_table
            );
        END IF;

        IF has_table_privilege('empiredb_readonly', v_rel, 'SELECT') THEN
            v_policy := v_table || '_readonly_select';
            EXECUTE format('DROP POLICY IF EXISTS %I ON public.%I', v_policy, v_table);
            EXECUTE format(
                'CREATE POLICY %I ON public.%I FOR SELECT TO empiredb_readonly USING (true)',
                v_policy, v_table
            );
        END IF;
    END LOOP;
END;
$$;

RESET ROLE;
