-- EmpireDB migration 043: outbound telemetry heartbeats and SLA snapshots
-- STAGED ONLY. Do not apply without explicit founder approval.
-- Append-only observer liveness and evidence-coverage history.
-- No runtime grants, DNS mutation, provisioning authority, or send authority.

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS public.outbound_telemetry_heartbeats (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scope_key TEXT NOT NULL DEFAULT 'empire',
    heartbeat_key TEXT NOT NULL,
    source_key TEXT NOT NULL,
    success BOOLEAN NOT NULL,
    coverage BOOLEAN,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    observed_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(scope_key, heartbeat_key)
);

CREATE INDEX IF NOT EXISTS idx_outbound_telemetry_heartbeats_source_time
    ON public.outbound_telemetry_heartbeats(
        scope_key, source_key, observed_at DESC
    );

CREATE TABLE IF NOT EXISTS public.outbound_telemetry_sla_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scope_key TEXT NOT NULL DEFAULT 'empire',
    snapshot_key TEXT NOT NULL,
    posture TEXT NOT NULL CHECK (
        posture IN ('CURRENT','PARTIAL','STALE','BLIND')
    ),
    required_sources JSONB NOT NULL DEFAULT '[]'::jsonb,
    critical_sources JSONB NOT NULL DEFAULT '[]'::jsonb,
    missing_sources JSONB NOT NULL DEFAULT '[]'::jsonb,
    stale_sources JSONB NOT NULL DEFAULT '[]'::jsonb,
    failed_sources JSONB NOT NULL DEFAULT '[]'::jsonb,
    partial_sources JSONB NOT NULL DEFAULT '[]'::jsonb,
    critical_blind BOOLEAN NOT NULL DEFAULT FALSE,
    critical_stale BOOLEAN NOT NULL DEFAULT FALSE,
    critical_partial BOOLEAN NOT NULL DEFAULT FALSE,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    mutation_authorized BOOLEAN NOT NULL DEFAULT FALSE,
    send_authorized BOOLEAN NOT NULL DEFAULT FALSE,
    observed_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(scope_key, snapshot_key),
    CHECK (mutation_authorized = FALSE),
    CHECK (send_authorized = FALSE)
);

CREATE INDEX IF NOT EXISTS idx_outbound_telemetry_sla_latest
    ON public.outbound_telemetry_sla_snapshots(
        scope_key, observed_at DESC
    );

CREATE INDEX IF NOT EXISTS idx_outbound_telemetry_sla_posture
    ON public.outbound_telemetry_sla_snapshots(
        scope_key, posture, observed_at DESC
    );

COMMENT ON TABLE public.outbound_telemetry_heartbeats IS
    'Append-only observer/source liveness evidence independent of email event volume.';
COMMENT ON TABLE public.outbound_telemetry_sla_snapshots IS
    'Append-only CURRENT/PARTIAL/STALE/BLIND telemetry coverage snapshots; never grants send authority.';

COMMIT;
