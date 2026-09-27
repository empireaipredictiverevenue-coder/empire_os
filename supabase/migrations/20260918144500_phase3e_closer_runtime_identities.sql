-- Phase 3E closer runtime identities and bounded work projection.
-- Local/staged only: login passwords remain NULL until production approval.
BEGIN;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_roles WHERE rolname='empire_closer_observer'
  ) THEN
    CREATE ROLE empire_closer_observer
      NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
      NOREPLICATION NOBYPASSRLS;
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_roles WHERE rolname='empire_closer_planner'
  ) THEN
    CREATE ROLE empire_closer_planner
      NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
      NOREPLICATION NOBYPASSRLS;
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_roles WHERE rolname='empire_closer_observer_login'
  ) THEN
    CREATE ROLE empire_closer_observer_login
      LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
      NOREPLICATION NOBYPASSRLS CONNECTION LIMIT 5;
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_roles WHERE rolname='empire_closer_planner_login'
  ) THEN
    CREATE ROLE empire_closer_planner_login
      LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
      NOREPLICATION NOBYPASSRLS CONNECTION LIMIT 5;
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_roles WHERE rolname='empire_closer_approver_login'
  ) THEN
    CREATE ROLE empire_closer_approver_login
      LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
      NOREPLICATION NOBYPASSRLS CONNECTION LIMIT 5;
  END IF;
END $$;

ALTER ROLE empire_closer_observer_login PASSWORD NULL;
ALTER ROLE empire_closer_planner_login PASSWORD NULL;
ALTER ROLE empire_closer_approver_login PASSWORD NULL;

GRANT USAGE ON SCHEMA public
  TO empire_closer_observer,empire_closer_planner,empire_closer_approver;

REVOKE empire_closer_observer,empire_closer_planner,empire_closer_approver
  FROM service_role;

GRANT empire_closer_observer TO empire_closer_observer_login;
GRANT empire_closer_planner TO empire_closer_planner_login;
GRANT empire_closer_approver TO empire_closer_approver_login;

ALTER ROLE empire_closer_observer_login SET statement_timeout='15s';
ALTER ROLE empire_closer_observer_login
  SET idle_in_transaction_session_timeout='30s';
ALTER ROLE empire_closer_planner_login SET statement_timeout='15s';
ALTER ROLE empire_closer_planner_login
  SET idle_in_transaction_session_timeout='30s';
ALTER ROLE empire_closer_approver_login SET statement_timeout='15s';
ALTER ROLE empire_closer_approver_login
  SET idle_in_transaction_session_timeout='30s';

CREATE OR REPLACE FUNCTION public.list_closer_work(p_limit integer DEFAULT 50)
RETURNS jsonb
LANGUAGE sql
SECURITY DEFINER
SET search_path=''
AS $$
  SELECT COALESCE(
    jsonb_agg(to_jsonb(q) ORDER BY q.received_at DESC),
    '[]'::jsonb
  )
  FROM (
    SELECT
      r.id AS reply_id,
      r.intent_id AS outbound_intent_id,
      r.classification,
      r.confidence,
      r.received_at,
      c.id AS case_id,
      c.state AS case_state,
      i.prospect_id,
      i.entity_id,
      i.buyer_id,
      i.opportunity_id,
      c.fulfilment_order_id
    FROM public.outbound_replies r
    JOIN public.outbound_intents i ON i.id=r.intent_id
    LEFT JOIN public.closer_cases c ON c.reply_id=r.id
    WHERE r.classification IN ('positive','question','objection')
      AND (c.id IS NULL OR c.state NOT IN ('won','lost'))
    ORDER BY r.received_at DESC
    LIMIT LEAST(GREATEST(COALESCE(p_limit,50),1),500)
  ) q;
$$;

REVOKE ALL ON FUNCTION public.list_closer_work(integer)
  FROM PUBLIC,anon,authenticated,service_role,
       empire_closer_observer,empire_closer_planner,empire_closer_approver;
GRANT EXECUTE ON FUNCTION public.list_closer_work(integer)
  TO empire_closer_observer,empire_closer_planner,service_role;

REVOKE ALL ON FUNCTION public.open_closer_case(uuid)
  FROM empire_closer_observer,empire_closer_approver;
GRANT EXECUTE ON FUNCTION public.open_closer_case(uuid)
  TO empire_closer_planner,service_role;

REVOKE ALL ON FUNCTION public.record_closer_recommendation(
  uuid,text,numeric,jsonb,text,text
) FROM empire_closer_observer,empire_closer_approver;
GRANT EXECUTE ON FUNCTION public.record_closer_recommendation(
  uuid,text,numeric,jsonb,text,text
) TO empire_closer_planner,service_role;

REVOKE ALL ON FUNCTION public.advance_closer_case(uuid,text,text,uuid,text)
  FROM empire_closer_observer,empire_closer_planner,service_role;
GRANT EXECUTE ON FUNCTION public.advance_closer_case(uuid,text,text,uuid,text)
  TO empire_closer_approver;

COMMENT ON ROLE empire_closer_observer IS
'Read-only closer work observer; no commercial mutation authority.';
COMMENT ON ROLE empire_closer_planner IS
'Closer planner; may open canonical cases and record recommendations only.';
COMMENT ON ROLE empire_closer_approver IS
'Human/governed closer approver; may advance allowed closer states only.';
COMMENT ON FUNCTION public.list_closer_work(integer) IS
'Bounded non-PII closer work projection from classified real replies.';

COMMIT;
