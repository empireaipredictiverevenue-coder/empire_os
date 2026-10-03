-- EmpireDB migration 036: outbound capacity reservation leases
-- STAGED ONLY. Do not apply without explicit founder approval.
-- Extends the append-only capacity ledger for cross-agent single-flight reservations.
-- No runtime grants, no data mutation, and no send authority are introduced here.

BEGIN;

ALTER TABLE public.outbound_capacity_ledger
    ADD COLUMN IF NOT EXISTS reservation_key TEXT,
    ADD COLUMN IF NOT EXISTS idempotency_key TEXT,
    ADD COLUMN IF NOT EXISTS lease_expires_at TIMESTAMPTZ;

CREATE UNIQUE INDEX IF NOT EXISTS idx_outbound_capacity_idempotency
    ON public.outbound_capacity_ledger(scope_key, idempotency_key)
    WHERE idempotency_key IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_outbound_capacity_reservation
    ON public.outbound_capacity_ledger(
        scope_key, reservation_key, recorded_at
    )
    WHERE reservation_key IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_outbound_capacity_expiring_reservations
    ON public.outbound_capacity_ledger(
        scope_key, lease_expires_at, mailbox_key
    )
    WHERE event_type = 'RESERVE'
      AND lease_expires_at IS NOT NULL;

ALTER TABLE public.outbound_capacity_ledger
    ADD CONSTRAINT outbound_capacity_reservation_identity_required
    CHECK (
        event_type NOT IN ('RESERVE','CONSUME','RELEASE')
        OR (
            reservation_key IS NOT NULL
            AND length(btrim(reservation_key)) > 0
            AND idempotency_key IS NOT NULL
            AND length(btrim(idempotency_key)) > 0
        )
    )
    NOT VALID;

ALTER TABLE public.outbound_capacity_ledger
    ADD CONSTRAINT outbound_capacity_reserve_lease_required
    CHECK (
        event_type <> 'RESERVE'
        OR lease_expires_at IS NOT NULL
    )
    NOT VALID;

COMMENT ON COLUMN public.outbound_capacity_ledger.reservation_key IS
    'Stable logical reservation identity spanning RESERVE/CONSUME/RELEASE events.';
COMMENT ON COLUMN public.outbound_capacity_ledger.idempotency_key IS
    'Globally unique per-scope append identity used to collapse retried capacity events.';
COMMENT ON COLUMN public.outbound_capacity_ledger.lease_expires_at IS
    'Expiry for RESERVE events; expired capacity requires an explicit append-only RELEASE recovery event.';

COMMIT;
