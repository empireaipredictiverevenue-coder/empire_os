-- Restore the least-privilege RLS read path required by standing outbound
-- approval. HELD until explicit founder database activation approval.
BEGIN;
SET LOCAL ROLE empiredb_migrator;

DO $outbound_review_visibility_guard$
BEGIN
  IF current_database() <> 'empiredb' THEN
    RAISE EXCEPTION 'EmpireDB required';
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM pg_catalog.pg_roles
    WHERE rolname='empire_outbound_approver'
      AND NOT rolcanlogin
      AND NOT rolsuper
      AND NOT rolbypassrls
  ) THEN
    RAISE EXCEPTION 'bounded outbound approver role required';
  END IF;

  IF pg_catalog.to_regclass('public.buyer_candidate_reviews') IS NULL THEN
    RAISE EXCEPTION 'buyer_candidate_reviews relation required';
  END IF;

  IF NOT pg_catalog.has_table_privilege(
    'empire_outbound_approver',
    'public.buyer_candidate_reviews',
    'SELECT'
  ) THEN
    RAISE EXCEPTION 'outbound approver SELECT grant required before RLS policy';
  END IF;

  IF pg_catalog.has_table_privilege(
    'empire_outbound_approver',
    'public.buyer_candidate_reviews',
    'INSERT'
  ) OR pg_catalog.has_table_privilege(
    'empire_outbound_approver',
    'public.buyer_candidate_reviews',
    'UPDATE'
  ) OR pg_catalog.has_table_privilege(
    'empire_outbound_approver',
    'public.buyer_candidate_reviews',
    'DELETE'
  ) THEN
    RAISE EXCEPTION 'outbound approver review authority must remain read-only';
  END IF;
END;
$outbound_review_visibility_guard$;

DO $outbound_review_visibility_policy$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_catalog.pg_policy p
    JOIN pg_catalog.pg_class c ON c.oid=p.polrelid
    JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
    WHERE n.nspname='public'
      AND c.relname='buyer_candidate_reviews'
      AND p.polname='buyer_candidate_reviews_empire_outbound_approver_select'
  ) THEN
    EXECUTE $policy$
      CREATE POLICY buyer_candidate_reviews_empire_outbound_approver_select
      ON public.buyer_candidate_reviews
      FOR SELECT
      TO empire_outbound_approver
      USING (true)
    $policy$;
  END IF;
END;
$outbound_review_visibility_policy$;

COMMENT ON POLICY buyer_candidate_reviews_empire_outbound_approver_select
ON public.buyer_candidate_reviews
IS 'Allows the bounded outbound approver to read the approved review row required by auto-approval freshness/personhood checks. Grants no review mutation authority.';

COMMIT;
