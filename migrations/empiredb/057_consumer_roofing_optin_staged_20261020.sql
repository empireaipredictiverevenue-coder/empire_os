-- CONSUMER057: STAGED ONLY. DO NOT APPLY TO PRODUCTION.
-- Independent founder DBA, privacy-owner and authenticated-email-service
-- authorisation required. No API grant, public collection or outbound mail.
-- Separate from company prospects, buyer leads, CRM, analytics and outreach.
BEGIN;
SET LOCAL statement_timeout='10s';
SET LOCAL lock_timeout='3s';

DO $guard$
BEGIN
  IF current_database() NOT IN ('empiredb', 'empire_consumer_optin_fixture') THEN
    RAISE EXCEPTION 'CONSUMER057_WRONG_DATABASE';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_catalog.pg_roles
    WHERE rolname='empiredb_migrator' AND NOT rolcanlogin
      AND NOT rolsuper AND NOT rolbypassrls
  ) THEN
    RAISE EXCEPTION 'CONSUMER057_MIGRATOR_CUSTODY_UNVERIFIED';
  END IF;
  IF pg_catalog.to_regclass('public.empire_consumer_subscriptions') IS NOT NULL
     OR pg_catalog.to_regclass('public.empire_consumer_consent_events') IS NOT NULL
     OR pg_catalog.to_regclass('public.empire_consumer_email_suppressions') IS NOT NULL
     OR pg_catalog.to_regprocedure('public.empire_consumer_consent_event_immutable()') IS NOT NULL
  THEN
    RAISE EXCEPTION 'CONSUMER057_OBJECT_ALREADY_EXISTS_REVIEW_FIRST';
  END IF;
END;
$guard$;

SET LOCAL ROLE empiredb_migrator;

-- Email lookups use a server-managed keyed HMAC, NOT raw SHA256, to resist
-- dictionary attacks. The encryption key is NOT stored in EmpireDB.
-- The subscription is purpose-specific to Empire AI's OWN BRAND updates.
-- A named-buyer referral requires an entirely separate original consent flow.
CREATE TABLE public.empire_consumer_subscriptions (
  subscription_id uuid PRIMARY KEY DEFAULT pg_catalog.gen_random_uuid(),
  tenant_scope text NOT NULL DEFAULT 'empire-ai.co.uk'
    CHECK (tenant_scope='empire-ai.co.uk'),
  email_lookup_hmac text NOT NULL
    CHECK (email_lookup_hmac ~ '^[a-f0-9]{64}$'),
  email_ciphertext bytea NOT NULL CHECK (octet_length(email_ciphertext) BETWEEN 40 AND 2048),
  email_key_reference text NOT NULL
    CHECK (email_key_reference ~ '^[a-z][a-z0-9_:-]{5,63}$'),
  purpose text NOT NULL DEFAULT 'empire_own_brand_homeowner_updates'
    CHECK (purpose='empire_own_brand_homeowner_updates'),
  offer_slug text NOT NULL DEFAULT 'roofing-cost-guide'
    CHECK (offer_slug='roofing-cost-guide'),
  consent_notice_version text NOT NULL
    CHECK (consent_notice_version='roofing-homeowner-updates-v1'),
  consent_capture_digest text NOT NULL
    CHECK (consent_capture_digest ~ '^[a-f0-9]{64}$'),
  source_evidence_kind text NOT NULL
    CHECK (source_evidence_kind='ORIGINAL_FIRST_PARTY_OPTIN_RECEIPT'),
  permission_state text NOT NULL DEFAULT 'pending_verification'
    CHECK (permission_state IN ('pending_verification','verified','unsubscribed','erased')),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  verified_at timestamptz,
  revoked_at timestamptz,
  erased_at timestamptz,
  CONSTRAINT empire_consumer_one_contact_per_purpose
    UNIQUE (tenant_scope, purpose, email_lookup_hmac),
  CHECK ((permission_state <> 'verified') OR verified_at IS NOT NULL),
  CHECK ((permission_state NOT IN ('unsubscribed','erased')) OR revoked_at IS NOT NULL),
  CHECK ((permission_state <> 'erased') OR erased_at IS NOT NULL)
);
COMMENT ON TABLE public.empire_consumer_subscriptions IS
  'STAGED: encrypted individually permissioned OWN BRAND email subscriptions, no contractor/referral rights, no active app role.';

-- Immutable evidence, not a marketing list. No emails, IPs, names, raw URLs,
-- untrusted UTM tags, browser identifiers or unencrypted addresses in events.
CREATE TABLE public.empire_consumer_consent_events (
  event_id uuid PRIMARY KEY DEFAULT pg_catalog.gen_random_uuid(),
  subscription_id uuid NOT NULL
    REFERENCES public.empire_consumer_subscriptions(subscription_id),
  consent_action text NOT NULL
    CHECK (consent_action IN ('opt_in_requested','opt_in_verified',
                             'unsubscribed','erasure_requested','erasure_completed')),
  purpose text NOT NULL DEFAULT 'empire_own_brand_homeowner_updates'
    CHECK (purpose='empire_own_brand_homeowner_updates'),
  notice_version text NOT NULL CHECK (notice_version='roofing-homeowner-updates-v1'),
  evidence_digest text NOT NULL CHECK (evidence_digest ~ '^[a-f0-9]{64}$'),
  evidence_method text NOT NULL
    CHECK (evidence_method IN ('ORIGINAL_BROWSER_CHOICE','VERIFIED_EMAIL_TOKEN',
                              'AUTHENTICATED_WITHDRAWAL','PRIVACY_OWNER_ERASURE')),
  observed_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

-- Tombstones protect against re-import/re-opt-in after an unsubscribe.
-- Retention and lawful deletion policy must be separately confirmed.
CREATE TABLE public.empire_consumer_email_suppressions (
  email_lookup_hmac text PRIMARY KEY
    CHECK (email_lookup_hmac ~ '^[a-f0-9]{64}$'),
  purpose text NOT NULL DEFAULT 'empire_own_brand_homeowner_updates'
    CHECK (purpose='empire_own_brand_homeowner_updates'),
  reason text NOT NULL CHECK (reason IN ('unsubscribe','privacy_request','complaint','bounce')),
  suppressed_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE INDEX empire_consumer_subs_by_state
  ON public.empire_consumer_subscriptions(permission_state, created_at);
CREATE INDEX empire_consumer_events_by_sub
  ON public.empire_consumer_consent_events(subscription_id, observed_at);

CREATE FUNCTION public.empire_consumer_consent_event_immutable()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER
SET search_path=pg_catalog
AS $function$
BEGIN
  RAISE EXCEPTION 'CONSUMER057_CONSENT_LOG_APPEND_ONLY';
END;
$function$;

CREATE TRIGGER empire_consumer_event_immutable
  BEFORE UPDATE OR DELETE ON public.empire_consumer_consent_events
  FOR EACH ROW EXECUTE FUNCTION public.empire_consumer_consent_event_immutable();

ALTER TABLE public.empire_consumer_subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.empire_consumer_subscriptions FORCE ROW LEVEL SECURITY;
ALTER TABLE public.empire_consumer_consent_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.empire_consumer_consent_events FORCE ROW LEVEL SECURITY;
ALTER TABLE public.empire_consumer_email_suppressions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.empire_consumer_email_suppressions FORCE ROW LEVEL SECURITY;

-- No policies and NO runtime grants. Dedicated operator-reviewed writer /
-- verification / withdrawal capabilities must be established separately.
REVOKE ALL ON TABLE public.empire_consumer_subscriptions FROM PUBLIC;
REVOKE ALL ON TABLE public.empire_consumer_consent_events FROM PUBLIC;
REVOKE ALL ON TABLE public.empire_consumer_email_suppressions FROM PUBLIC;
REVOKE ALL ON FUNCTION public.empire_consumer_consent_event_immutable() FROM PUBLIC;

COMMENT ON TABLE public.empire_consumer_email_suppressions IS
  'STAGED: privacy-protective purpose-specific keyed tombstones. Not a buyer export or outreach permission.';

COMMIT;
