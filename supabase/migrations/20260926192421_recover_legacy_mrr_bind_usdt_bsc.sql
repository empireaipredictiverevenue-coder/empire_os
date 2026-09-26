-- Recover legacy MRR SKUs into the canonical commercial catalog.
-- Canonical forward settlement rail: USDT on BSC.
-- Historical USDC/Solana evidence is preserved and remains non-canonical.

DO $$
DECLARE
  r record;
  resolved_name text;
  price_basis jsonb;
  evidence_refs jsonb;
BEGIN
  FOR r IN
    WITH recovered AS (
      SELECT
        lower(COALESCE(p.tier,m.tier)) AS product_code,
        COALESCE(p.product_slug,m.product_name) AS product_slug,
        COALESCE(p.tier,m.tier) AS tier,
        p.mrr_usd AS pricing_mrr_usd,
        p.checks_per_month,
        p.narrative_enabled,
        p.what_if_enabled,
        p.features AS pricing_features,
        p.updated_at AS pricing_updated_at,
        m.monthly_price_usd AS metadata_mrr_usd,
        m.display_name,
        m.description,
        m.price_per_unit,
        m.features AS metadata_features,
        m.is_active AS metadata_active,
        m.is_public AS metadata_public,
        m.updated_at AS metadata_updated_at,
        CASE
          WHEN p.tier IS NULL THEN 'METADATA_ONLY'
          WHEN m.tier IS NULL THEN 'PRICING_ONLY'
          WHEN p.mrr_usd = m.monthly_price_usd THEN 'MATCH'
          ELSE 'PRICE_CONFLICT'
        END AS recovery_state
      FROM public.product_pricing p
      FULL OUTER JOIN public.product_metadata m
        ON m.tier=p.tier
    )
    SELECT *
    FROM recovered
    ORDER BY product_slug,tier
  LOOP
    resolved_name := COALESCE(
      NULLIF(trim(COALESCE(r.display_name,'')),''),
      initcap(replace(r.product_code,'_',' '))
    );

    price_basis := CASE r.recovery_state
      WHEN 'MATCH' THEN jsonb_build_object(
        'state','VERIFIED',
        'unit','per_month',
        'currency','USD',
        'basis_type','legacy_recovery_consensus',
        'source_type','legacy_consensus',
        'amount_cents',round(r.pricing_mrr_usd * 100)::bigint,
        'pricing_updated_at',r.pricing_updated_at,
        'metadata_updated_at',r.metadata_updated_at,
        'commercial_approval_state','REQUIRES_FOUNDER_ECONOMICS_REVIEW'
      )
      WHEN 'PRICE_CONFLICT' THEN jsonb_build_object(
        'state','CONFLICT',
        'unit','per_month',
        'currency','USD',
        'basis_type','legacy_recovery_conflict',
        'pricing_candidate_cents',round(r.pricing_mrr_usd * 100)::bigint,
        'metadata_candidate_cents',round(r.metadata_mrr_usd * 100)::bigint,
        'pricing_updated_at',r.pricing_updated_at,
        'metadata_updated_at',r.metadata_updated_at,
        'commercial_approval_state','REQUIRES_FOUNDER_PRICE_RESOLUTION'
      )
      WHEN 'PRICING_ONLY' THEN jsonb_build_object(
        'state','UNKNOWN',
        'unit','per_month',
        'currency','USD',
        'basis_type','legacy_single_source',
        'source_type','product_pricing',
        'candidate_amount_cents',round(r.pricing_mrr_usd * 100)::bigint,
        'source_updated_at',r.pricing_updated_at,
        'commercial_approval_state','REQUIRES_FOUNDER_ECONOMICS_REVIEW'
      )
      ELSE jsonb_build_object(
        'state','UNKNOWN',
        'unit','per_month',
        'currency','USD',
        'basis_type','legacy_single_source',
        'source_type','product_metadata',
        'candidate_amount_cents',round(r.metadata_mrr_usd * 100)::bigint,
        'source_updated_at',r.metadata_updated_at,
        'commercial_approval_state','REQUIRES_FOUNDER_ECONOMICS_REVIEW'
      )
    END;

    evidence_refs := to_jsonb(array_remove(ARRAY[
      CASE WHEN r.pricing_mrr_usd IS NOT NULL
        THEN 'legacy:product_pricing:' || r.tier END,
      CASE WHEN r.metadata_mrr_usd IS NOT NULL
        THEN 'legacy:product_metadata:' || r.tier END,
      'founder_approval:2026-09-26:recovery_and_usdt_bsc_binding_only'
    ]::text[],NULL));

    PERFORM public.register_commercial_product_identity(
      r.product_code,
      resolved_name,
      'recovered_mrr',
      'monthly_subscription',
      jsonb_build_object(
        'currency','USD',
        'settlement','USDT_BSC',
        'settlement_asset','USDT',
        'settlement_network','BSC',
        'settlement_chain_id',56,
        'legacy_product_slug',r.product_slug,
        'legacy_tier',r.tier,
        'recovery_state',r.recovery_state,
        'checks_per_month',r.checks_per_month,
        'narrative_enabled',COALESCE(r.narrative_enabled,false),
        'what_if_enabled',COALESCE(r.what_if_enabled,false),
        'features',COALESCE(r.metadata_features,r.pricing_features,'[]'::jsonb),
        'description',r.description,
        'price_per_unit',r.price_per_unit,
        'legacy_metadata_active',r.metadata_active,
        'legacy_metadata_public',r.metadata_public,
        'commercial_activation','PENDING_ECONOMICS_REVIEW',
        'actual_revenue',false
      ),
      jsonb_build_object(
        'source','legacy_mrr_recovery',
        'recovery_batch','legacy_mrr_usdt_bsc_v1',
        'recovered_at',clock_timestamp(),
        'founder_approved_recovery',true,
        'founder_approved_settlement_rail','USDT_BSC',
        'economics_founder_approved',false,
        'historical_usdc_solana_preserved',true,
        'actual_revenue',false
      ),
      'chatgpt_revenue_recovery'
    );

    IF NOT EXISTS (
      SELECT 1
      FROM public.commercial_product_versions v
      JOIN public.commercial_products cp ON cp.id=v.product_id
      WHERE cp.product_code=r.product_code
        AND v.provenance->>'recovery_batch'='legacy_mrr_usdt_bsc_v1'
    ) THEN
      PERFORM public.propose_commercial_product_version(
        r.product_code,
        'monthly_subscription',
        'USD',
        price_basis,
        jsonb_build_object(
          'state','UNKNOWN',
          'reason','acquisition_cost_not_recovered_from_legacy_sources'
        ),
        jsonb_build_object(
          'state','UNKNOWN',
          'reason','fulfilment_cost_not_recovered_from_legacy_sources'
        ),
        jsonb_build_object(
          'state','UNKNOWN',
          'reason','margin_policy_not_recovered_from_legacy_sources'
        ),
        jsonb_build_object(
          'source','legacy_mrr_recovery',
          'recovery_batch','legacy_mrr_usdt_bsc_v1',
          'legacy_product_slug',r.product_slug,
          'legacy_tier',r.tier,
          'recovery_state',r.recovery_state,
          'settlement','USDT_BSC',
          'founder_approved_recovery',true,
          'economics_founder_approved',false,
          'actual_revenue',false
        ),
        evidence_refs,
        clock_timestamp(),
        NULL,
        'chatgpt_revenue_recovery'
      );
    END IF;
  END LOOP;
END
$$;

-- Bind every active canonical product to the current settlement rail without
-- changing its pricing currency or recognizing revenue.
UPDATE public.commercial_products
SET configuration =
      COALESCE(configuration,'{}'::jsonb)
      || jsonb_build_object(
        'settlement','USDT_BSC',
        'settlement_asset','USDT',
        'settlement_network','BSC',
        'settlement_chain_id',56,
        'settlement_policy_state','FOUNDER_APPROVED',
        'settlement_policy_approved_at','2026-09-26',
        'settlement_fx_state',
          CASE
            WHEN currency='USD' THEN 'USD_DENOMINATED_TERMS'
            ELSE 'FX_REQUIRED_AT_BINDING_TERMS'
          END
      ),
    provenance =
      COALESCE(provenance,'{}'::jsonb)
      || jsonb_build_object(
        'settlement_rail_binding',
        jsonb_build_object(
          'asset','USDT',
          'network','BSC',
          'chain_id',56,
          'approved_at','2026-09-26',
          'legacy_usdc_solana_forward_use',false,
          'historical_evidence_preserved',true
        )
      ),
    updated_at=clock_timestamp()
WHERE active=true;

-- Demo/test subscriptions must never appear as real active MRR.
UPDATE public.product_subscriptions
SET subscription_status='CANCELED',
    notes=concat_ws(
      E'\n',
      NULLIF(notes,''),
      CASE
        WHEN customer_account_id LIKE 'demo_%'
          THEN '[2026-09-26] Recovery classification: DEMO_ONLY_NON_REVENUE.'
        WHEN customer_account_id LIKE 'e2e_%'
          THEN '[2026-09-26] Recovery classification: E2E_TEST_ONLY_NON_REVENUE.'
      END
    ),
    updated_at=clock_timestamp()
WHERE subscription_status='ACTIVE'
  AND (
    customer_account_id LIKE 'demo_%'
    OR customer_account_id LIKE 'e2e_%'
  );

COMMENT ON TABLE public.crypto_payment_requests IS
  'LEGACY USDC/Solana payment-request evidence. Do not use for new payments or revenue recognition. Canonical rail is public.bsc_payment_requests with amount_usdt.';
COMMENT ON TABLE public.empire_revenue_ledger IS
  'LEGACY/accrual revenue evidence. Historical usdc_amount is preserved. Do not treat accrued/test rows as verified cash. Canonical settlement evidence is BSC/USDT.';
COMMENT ON TABLE public.contractor_priority_subscriptions IS
  'LEGACY subscription/payment evidence containing historical Solana/USDC fields. Forward settlement rail is USDT on BSC.';
COMMENT ON TABLE public.contractor_subscriptions IS
  'LEGACY subscription/payment evidence containing historical USDC fields. Forward settlement rail is USDT on BSC.';
COMMENT ON TABLE public.subscription_tiers IS
  'LEGACY tier table containing historical monthly_usdc naming. Recovered products are bound in commercial_products/commercial_product_versions with USDT/BSC settlement.';
COMMENT ON TABLE public.dispatch_invoices IS
  'LEGACY invoice evidence containing historical amount_usdc naming. Forward settlement rail is USDT on BSC.';
COMMENT ON TABLE public.payout_log IS
  'LEGACY payout evidence containing historical amount_usdc naming. Forward settlement rail is USDT on BSC.';

COMMENT ON COLUMN public.crypto_payment_requests.amount_usdc IS
  'LEGACY historical USDC amount. New payment requests must use public.bsc_payment_requests.amount_usdt.';
COMMENT ON COLUMN public.crypto_payment_requests.paid_amount_usdc IS
  'LEGACY historical USDC paid amount. New payment evidence must use BSC/USDT canonical tables.';
COMMENT ON COLUMN public.empire_revenue_ledger.usdc_amount IS
  'LEGACY historical/accrual USDC-denominated field; preserved for evidence only.';
COMMENT ON COLUMN public.subscription_tiers.monthly_usdc IS
  'LEGACY price field; recovered tier economics are represented in commercial_product_versions and settle via USDT/BSC.';
