-- EmpireDB migration 040: outbound account saturation dimensions
-- STAGED ONLY. Do not apply without explicit founder approval.
-- Extends append-only contact-pressure evidence for company-group and corridor governance.
-- No runtime grants, mutation authority, or send authority.

BEGIN;

ALTER TABLE public.outbound_contact_pressure_events
    ADD COLUMN IF NOT EXISTS parent_company_key TEXT,
    ADD COLUMN IF NOT EXISTS corridor_key TEXT,
    ADD COLUMN IF NOT EXISTS event_kind TEXT NOT NULL DEFAULT 'outbound_touch';

CREATE INDEX IF NOT EXISTS idx_outbound_contact_pressure_parent
    ON public.outbound_contact_pressure_events(
        scope_key, parent_company_key, occurred_at DESC
    )
    WHERE parent_company_key IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_outbound_contact_pressure_corridor
    ON public.outbound_contact_pressure_events(
        scope_key, corridor_key, occurred_at DESC
    )
    WHERE corridor_key IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_outbound_contact_pressure_company_kind
    ON public.outbound_contact_pressure_events(
        scope_key, company_key, event_kind, occurred_at DESC
    );

ALTER TABLE public.outbound_contact_pressure_events
    ADD CONSTRAINT outbound_contact_pressure_event_kind_nonempty
    CHECK (length(btrim(event_kind)) > 0)
    NOT VALID;

COMMENT ON COLUMN public.outbound_contact_pressure_events.parent_company_key IS
    'Canonical parent-group identity used to prevent cross-subsidiary agent pile-on.';
COMMENT ON COLUMN public.outbound_contact_pressure_events.corridor_key IS
    'Stable commercial/geographic corridor key used for bounded corridor pacing.';
COMMENT ON COLUMN public.outbound_contact_pressure_events.event_kind IS
    'Observed touch or conversation event used by account saturation replay.';

COMMIT;
