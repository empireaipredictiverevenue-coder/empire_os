-- Canonical append-only prospect consent evidence.
-- Staged only: no production apply or outbound activation.
BEGIN;

CREATE TABLE IF NOT EXISTS public.prospect_consent_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  prospect_id uuid NOT NULL
    REFERENCES public.prospects(id) ON DELETE RESTRICT,
  channel text NOT NULL CHECK (
    channel IN ('email','sms','voice','a2a')
  ),
  decision text NOT NULL CHECK (
    decision IN ('granted','revoked')
  ),
  source text NOT NULL,
  evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
  occurred_at timestamptz NOT NULL,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE INDEX IF NOT EXISTS idx_prospect_consent_latest
  ON public.prospect_consent_events(
    prospect_id,channel,occurred_at DESC,created_at DESC
  );

ALTER TABLE public.prospect_consent_events ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.prospect_consent_events
FROM PUBLIC,anon,authenticated;

GRANT SELECT ON public.prospect_consent_events TO service_role;

CREATE OR REPLACE VIEW public.prospect_consent_current AS
SELECT DISTINCT ON (prospect_id,channel)
  prospect_id,
  channel,
  decision,
  source,
  evidence,
  occurred_at,
  created_at
FROM public.prospect_consent_events
ORDER BY prospect_id,channel,occurred_at DESC,created_at DESC;

REVOKE ALL ON public.prospect_consent_current
FROM PUBLIC,anon,authenticated;

GRANT SELECT ON public.prospect_consent_current TO service_role;

COMMIT;
