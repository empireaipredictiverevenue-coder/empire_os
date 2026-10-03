-- EmpireOS outbound deliverability least-privilege roles
-- STAGED ONLY. Apply only after migrations 033-041 are present and
-- explicit authority-expansion approval has been given.
-- Creates NOLOGIN permission roles only. No credentials are created.

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_roles
        WHERE rolname = 'empire_outbound_deliverability_reader'
    ) THEN
        CREATE ROLE empire_outbound_deliverability_reader
            NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOINHERIT NOREPLICATION NOBYPASSRLS;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_roles
        WHERE rolname = 'empire_outbound_deliverability_writer'
    ) THEN
        CREATE ROLE empire_outbound_deliverability_writer
            NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOINHERIT NOREPLICATION NOBYPASSRLS;
    END IF;
END
$$;

REVOKE ALL ON SCHEMA public
    FROM empire_outbound_deliverability_reader,
         empire_outbound_deliverability_writer;

GRANT USAGE ON SCHEMA public
    TO empire_outbound_deliverability_reader,
       empire_outbound_deliverability_writer;

GRANT SELECT ON
    public.outbound_deliverability_observations,
    public.outbound_ringleader_decisions,
    public.outbound_sender_pool_observations,
    public.outbound_provider_policy_snapshots,
    public.outbound_reputation_economic_events,
    public.outbound_contact_pressure_events,
    public.outbound_policy_manifests,
    public.outbound_policy_shadow_runs,
    public.outbound_transports,
    public.outbound_domains,
    public.outbound_mailboxes,
    public.outbound_sender_pools,
    public.outbound_pool_members,
    public.outbound_capacity_ledger,
    public.outbound_seed_mailboxes,
    public.outbound_source_reputation_events,
    public.outbound_source_reputation_snapshots,
    public.outbound_content_family_events,
    public.outbound_content_family_snapshots,
    public.outbound_claim_verification_events,
    public.outbound_fleet_readiness_certificates,
    public.outbound_telemetry_heartbeats,
    public.outbound_telemetry_sla_snapshots
TO empire_outbound_deliverability_reader;

-- The current observer writer persists only raw deliverability observations
-- and Ringleader decisions. It needs SELECT for idempotent read-back and INSERT.
GRANT SELECT, INSERT ON
    public.outbound_deliverability_observations,
    public.outbound_ringleader_decisions
TO empire_outbound_deliverability_writer;

REVOKE UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER ON
    public.outbound_deliverability_observations,
    public.outbound_ringleader_decisions
FROM empire_outbound_deliverability_writer;

-- Explicitly deny the evidence writer access to every other outbound table.
REVOKE ALL ON
    public.outbound_sender_pool_observations,
    public.outbound_provider_policy_snapshots,
    public.outbound_reputation_economic_events,
    public.outbound_contact_pressure_events,
    public.outbound_policy_manifests,
    public.outbound_policy_shadow_runs,
    public.outbound_transports,
    public.outbound_domains,
    public.outbound_mailboxes,
    public.outbound_sender_pools,
    public.outbound_pool_members,
    public.outbound_capacity_ledger,
    public.outbound_seed_mailboxes,
    public.outbound_source_reputation_events,
    public.outbound_source_reputation_snapshots,
    public.outbound_content_family_events,
    public.outbound_content_family_snapshots,
    public.outbound_claim_verification_events,
    public.outbound_fleet_readiness_certificates,
    public.outbound_telemetry_heartbeats,
    public.outbound_telemetry_sla_snapshots
FROM empire_outbound_deliverability_writer;
