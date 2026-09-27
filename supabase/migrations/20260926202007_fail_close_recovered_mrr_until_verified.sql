-- Fail-close recovered legacy MRR SKUs until economics/runtime binding is verified.
-- Recovery records remain preserved and queryable; no product/version evidence is deleted.

UPDATE public.commercial_products
SET active=false,
    configuration =
      COALESCE(configuration,'{}'::jsonb)
      || jsonb_build_object(
        'commercial_activation','RECOVERED_INACTIVE_PENDING_VERIFICATION',
        'activation_authority','founder_or_verified_catalog_process',
        'sellable_now',false,
        'actual_revenue',false
      ),
    provenance =
      COALESCE(provenance,'{}'::jsonb)
      || jsonb_build_object(
        'recovery_activation_guard',
        jsonb_build_object(
          'applied_at',clock_timestamp(),
          'actor','chatgpt_revenue_recovery',
          'reason','recovered_legacy_sku_requires_verified_economics_and_runtime_binding',
          'active_set_false',true,
          'payment_mutated',false,
          'revenue_recognized',false
        )
      ),
    updated_at=clock_timestamp()
WHERE provenance->>'recovery_batch'='legacy_mrr_usdt_bsc_v1'
  AND (
    catalog_state <> 'VERIFIED'
    OR NOT EXISTS (
      SELECT 1
      FROM public.commercial_product_versions v
      WHERE v.product_id=public.commercial_products.id
        AND v.version_state='VERIFIED'
    )
  );
