-- EmpireOS Economic Signal Fabric canonical source identities.
--
-- PREPARED ONLY.
-- Do not apply without explicit founder approval.
--
-- These rows establish provenance identities only.
-- They grant no execution/commercial/payment authority.

INSERT INTO public.intelligence_sources (
    source_key,
    source_type,
    display_name,
    authority_score,
    enabled,
    metadata
)
VALUES
(
    'empire.revenue_leak.observed.v1',
    'first_party',
    'Empire Observed Revenue Leak',
    0.5000,
    true,
    '{"truth_class":"OBSERVED","execution_authority":"none","economic_signal_type":"revenue_leak"}'::jsonb
),
(
    'empire.idle_asset.observed.v1',
    'first_party',
    'Empire Observed Idle Asset',
    0.5000,
    true,
    '{"truth_class":"OBSERVED","execution_authority":"none","economic_signal_type":"idle_asset"}'::jsonb
),
(
    'empire.market_gap.observed.v1',
    'market',
    'Empire Observed Market Gap',
    0.5000,
    true,
    '{"truth_class":"OBSERVED","execution_authority":"none","economic_signal_type":"market_gap"}'::jsonb
),
(
    'empire.idle_waste.observed.v1',
    'first_party',
    'Empire Observed Idle Waste',
    0.5000,
    true,
    '{"truth_class":"OBSERVED","execution_authority":"none","economic_signal_type":"idle_waste"}'::jsonb
)
ON CONFLICT (source_key)
DO NOTHING;
