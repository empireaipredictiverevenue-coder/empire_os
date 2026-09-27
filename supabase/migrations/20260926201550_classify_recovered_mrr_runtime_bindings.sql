-- Classify recovered legacy MRR products against the modern EmpireOS architecture.
-- Recovery metadata only: no pricing approval, no payment mutation,
-- no revenue recognition, and no automatic commercial activation.

WITH mapping(legacy_slug,recovery_decision,modern_target,commercial_priority,notes) AS (
  VALUES
    ('ai_closer','MERGE_MODERNIZE','buyer_conversation_engine','HIGH',
      'Retain tier concepts only as commercial packaging candidates; runtime capability is the governed Buyer Conversation / Closer system.'),
    ('all_products','HOLD_REDESIGN','commercial_bundle_framework','LOW',
      'Legacy all-access bundle is too broad to activate until every included product is independently verified and entitlement boundaries are defined.'),
    ('analyzer','HOLD_REVIEW','intelligence_fabric','LOW',
      'Useful intelligence components may be reusable, but the legacy OSINT packaging needs privacy, data-source, entitlement and product-scope review.'),
    ('buyer_spy','MERGE_RENAME','buyer_intelligence_and_competitive_intelligence','MEDIUM',
      'Merge useful intent/transcript/competitive capabilities; retire the legacy Buyer Spy naming from customer-facing packaging.'),
    ('compliant','MODERNIZE','compliance_and_outbound_governance','HIGH',
      'Strong reusable B2B compliance capability; bind to opt-out, suppression, quiet-hours, audit and governed outbound controls.'),
    ('content_pulse','MERGE','content_protection','HIGH',
      'Merge into canonical Content Decay & Cannibalisation Monitor / Search Growth Command rather than duplicate a separate content product.'),
    ('contractor_exchange','MERGE','commercial_exchange','HIGH',
      'Merge legacy contractor exchange packaging into current Commercial Exchange seats; do not carry legacy prices across automatically.'),
    ('data_vault','HOLD_MERGE','intelligence_fabric_storage','MEDIUM',
      'Retain data-retention/API concepts but merge with current governed intelligence storage rather than revive a disconnected vault product.'),
    ('elite_scraper','MERGE_REPRICE','signal_fabric_and_search_fabric','MEDIUM',
      'Core collection capability belongs to Signal/Search Fabric. Legacy prices conflict and must not be activated without founder price resolution.'),
    ('forecast','MERGE','predictive_intelligence','HIGH',
      'Merge legacy forecasting tiers into Predictive Intelligence / Predictive Revenue capabilities and current enterprise packaging.'),
    ('hexstrike','HOLD_NONCORE','security_tooling','LOW',
      'Security tooling can remain internal/enterprise-support capability; not a current core revenue priority.'),
    ('inbound_router','MODERNIZE','voice_gateway_and_buyer_allocation','HIGH',
      'Modernize as governed inbound call routing, AI triage, buyer allocation and metered routing SaaS.'),
    ('lead_score','MERGE','lead_scoring_v2_and_omega','HIGH',
      'Merge into current Lead Scoring v2 / Omega qualification and expose only governed product/API surfaces.'),
    ('market_eye','MERGE','market_sweeps_revenue_pulse_competitive_intelligence','HIGH',
      'Merge into Market Sweeps, Revenue Pulse and competitive intelligence rather than duplicate market-monitoring logic.'),
    ('meetily','ARCHIVE_NONCORE','none','LOW',
      'Meeting assistant is non-core to Predictive Revenue and has conflicting legacy pricing; archive unless a later strategic case is approved.'),
    ('seo_optimizer','MERGE','search_growth_command','HIGH',
      'Merge into current Search Intelligence suite and Search Growth Command; preserve viable tier concepts only where current deliverables support them.'),
    ('sovereign_agi_matrix','ARCHIVE_MERGE_INTERNAL','cortex_and_executive_intelligence','LOW',
      'Retire outdated AGI product branding; any useful internals belong inside Cortex / executive intelligence, not as a separate product.'),
    ('strike_campaigns','MERGE_MODERNIZE','outbound_governor_and_campaign_execution','HIGH',
      'Merge into governed outbound/campaign execution with suppression, consent, quiet-hours and approval boundaries.'),
    ('white_label','MODERNIZE','white_label_platform','HIGH',
      'Retain white-label commercial concept; require tenant isolation, entitlement, branding, support and economics verification before activation.')
)
UPDATE public.commercial_products cp
SET configuration =
      COALESCE(cp.configuration,'{}'::jsonb)
      || jsonb_build_object(
        'recovery_decision',m.recovery_decision,
        'modern_target',m.modern_target,
        'commercial_priority',m.commercial_priority,
        'recovery_notes',m.notes,
        'runtime_binding_state',
          CASE
            WHEN m.recovery_decision LIKE 'ARCHIVE%' THEN 'ARCHIVED_FROM_ACTIVATION'
            WHEN m.recovery_decision LIKE 'HOLD%' THEN 'HOLD'
            ELSE 'READY_FOR_RUNTIME_BINDING_REVIEW'
          END,
        'price_carry_forward_authorized',false,
        'commercial_activation','PENDING_ECONOMICS_REVIEW',
        'actual_revenue',false
      ),
    provenance =
      COALESCE(cp.provenance,'{}'::jsonb)
      || jsonb_build_object(
        'recovery_classification',
        jsonb_build_object(
          'decision',m.recovery_decision,
          'modern_target',m.modern_target,
          'classified_at',clock_timestamp(),
          'actor','chatgpt_revenue_recovery',
          'price_mutated',false,
          'payment_mutated',false,
          'actual_revenue',false
        )
      ),
    updated_at=clock_timestamp()
FROM mapping m
WHERE cp.provenance->>'recovery_batch'='legacy_mrr_usdt_bsc_v1'
  AND cp.configuration->>'legacy_product_slug'=m.legacy_slug;
