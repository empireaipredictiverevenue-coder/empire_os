-- Empire Data Cloud — GTM execution queue runtime
-- Migration: empiredb/007_gtm_execution_queue.sql
-- Source of truth: canonical live GTM queue contract.
-- Portable EmpireDB security: private DB, explicit app execute grants, SECURITY INVOKER.

ALTER TABLE public.gtm_jobs
    ADD COLUMN IF NOT EXISTS worker_id TEXT,
    ADD COLUMN IF NOT EXISTS lease_token UUID,
    ADD COLUMN IF NOT EXISTS lease_expires_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS heartbeat_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS next_attempt_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS last_error TEXT,
    ADD COLUMN IF NOT EXISTS idempotency_key TEXT,
    ADD COLUMN IF NOT EXISTS max_attempts INTEGER NOT NULL DEFAULT 5,
    ADD COLUMN IF NOT EXISTS created_by TEXT NOT NULL DEFAULT 'gtm_engine',
    ADD COLUMN IF NOT EXISTS queued_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS cancelled_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS cancel_reason TEXT;

CREATE INDEX IF NOT EXISTS idx_gtm_jobs_lease
    ON public.gtm_jobs (lease_expires_at)
    WHERE status = 'running';

CREATE INDEX IF NOT EXISTS idx_gtm_jobs_queue
    ON public.gtm_jobs (status, priority DESC, next_attempt_at, created_at);

CREATE INDEX IF NOT EXISTS idx_gtm_jobs_worker
    ON public.gtm_jobs (worker_id, heartbeat_at DESC);

CREATE UNIQUE INDEX IF NOT EXISTS uq_gtm_jobs_idempotency_key
    ON public.gtm_jobs (idempotency_key)
    WHERE idempotency_key IS NOT NULL;

CREATE OR REPLACE FUNCTION public.claim_next_gtm_job(
    p_worker_id TEXT,
    p_lease_seconds INTEGER DEFAULT 300
)
RETURNS SETOF public.gtm_jobs
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, public
AS $$
DECLARE
    v_job public.gtm_jobs;
BEGIN
    IF p_worker_id IS NULL OR length(trim(p_worker_id)) = 0 THEN
        RAISE EXCEPTION 'worker_id is required';
    END IF;

    IF p_lease_seconds < 30 OR p_lease_seconds > 3600 THEN
        RAISE EXCEPTION 'lease_seconds must be between 30 and 3600';
    END IF;

    UPDATE public.gtm_jobs
       SET status = 'queued',
           worker_id = NULL,
           lease_token = NULL,
           lease_expires_at = NULL,
           heartbeat_at = NULL,
           updated_at = now()
     WHERE status = 'running'
       AND lease_expires_at IS NOT NULL
       AND lease_expires_at < now();

    SELECT *
      INTO v_job
      FROM public.gtm_jobs
     WHERE status = 'queued'
       AND attempts < max_attempts
       AND (next_attempt_at IS NULL OR next_attempt_at <= now())
       AND (requires_approval = FALSE OR approved_at IS NOT NULL)
     ORDER BY priority DESC, created_at ASC
     FOR UPDATE SKIP LOCKED
     LIMIT 1;

    IF NOT FOUND THEN
        RETURN;
    END IF;

    UPDATE public.gtm_jobs
       SET status = 'running',
           worker_id = p_worker_id,
           lease_token = gen_random_uuid(),
           lease_expires_at = now() + make_interval(secs => p_lease_seconds),
           heartbeat_at = now(),
           attempts = attempts + 1,
           started_at = COALESCE(started_at, now()),
           updated_at = now()
     WHERE id = v_job.id
     RETURNING * INTO v_job;

    RETURN NEXT v_job;
END;
$$;

CREATE OR REPLACE FUNCTION public.heartbeat_gtm_job(
    p_job_id UUID,
    p_worker_id TEXT,
    p_lease_token UUID,
    p_lease_seconds INTEGER DEFAULT 300
)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, public
AS $$
DECLARE
    v_updated INTEGER;
BEGIN
    IF p_lease_seconds < 30 OR p_lease_seconds > 3600 THEN
        RAISE EXCEPTION 'lease_seconds must be between 30 and 3600';
    END IF;

    UPDATE public.gtm_jobs
       SET heartbeat_at = now(),
           lease_expires_at = now() + make_interval(secs => p_lease_seconds),
           updated_at = now()
     WHERE id = p_job_id
       AND worker_id = p_worker_id
       AND lease_token = p_lease_token
       AND status = 'running'
       AND (lease_expires_at IS NULL OR lease_expires_at >= now());

    GET DIAGNOSTICS v_updated = ROW_COUNT;
    RETURN v_updated = 1;
END;
$$;

CREATE OR REPLACE FUNCTION public.complete_gtm_job(
    p_job_id UUID,
    p_worker_id TEXT,
    p_lease_token UUID,
    p_result JSONB DEFAULT '{}'::jsonb
)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, public
AS $$
DECLARE
    v_updated INTEGER;
BEGIN
    UPDATE public.gtm_jobs
       SET status = 'completed',
           result = COALESCE(p_result, '{}'::jsonb),
           worker_id = NULL,
           lease_token = NULL,
           lease_expires_at = NULL,
           heartbeat_at = now(),
           completed_at = now(),
           updated_at = now()
     WHERE id = p_job_id
       AND worker_id = p_worker_id
       AND lease_token = p_lease_token
       AND status = 'running';

    GET DIAGNOSTICS v_updated = ROW_COUNT;
    RETURN v_updated = 1;
END;
$$;

CREATE OR REPLACE FUNCTION public.fail_gtm_job(
    p_job_id UUID,
    p_worker_id TEXT,
    p_lease_token UUID,
    p_error TEXT,
    p_retry_delay_seconds INTEGER DEFAULT 60,
    p_result JSONB DEFAULT '{}'::jsonb
)
RETURNS TEXT
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, public
AS $$
DECLARE
    v_job public.gtm_jobs;
    v_next_status TEXT;
BEGIN
    SELECT *
      INTO v_job
      FROM public.gtm_jobs
     WHERE id = p_job_id
       AND worker_id = p_worker_id
       AND lease_token = p_lease_token
       AND status = 'running'
     FOR UPDATE;

    IF NOT FOUND THEN
        RETURN 'lease_invalid';
    END IF;

    IF v_job.attempts >= v_job.max_attempts THEN
        v_next_status := 'failed';
    ELSE
        v_next_status := 'queued';
    END IF;

    UPDATE public.gtm_jobs
       SET status = v_next_status,
           last_error = left(COALESCE(p_error, 'unknown execution error'), 4000),
           result = COALESCE(p_result, '{}'::jsonb),
           next_attempt_at = CASE
               WHEN v_next_status = 'queued'
               THEN now() + make_interval(secs => GREATEST(p_retry_delay_seconds, 5))
               ELSE NULL
           END,
           worker_id = NULL,
           lease_token = NULL,
           lease_expires_at = NULL,
           heartbeat_at = now(),
           completed_at = CASE
               WHEN v_next_status = 'failed' THEN now()
               ELSE NULL
           END,
           updated_at = now()
     WHERE id = v_job.id;

    RETURN v_next_status;
END;
$$;

REVOKE ALL ON FUNCTION public.claim_next_gtm_job(TEXT, INTEGER) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.heartbeat_gtm_job(UUID, TEXT, UUID, INTEGER) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.complete_gtm_job(UUID, TEXT, UUID, JSONB) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.fail_gtm_job(UUID, TEXT, UUID, TEXT, INTEGER, JSONB) FROM PUBLIC;

GRANT EXECUTE ON FUNCTION public.claim_next_gtm_job(TEXT, INTEGER) TO empiredb_app;
GRANT EXECUTE ON FUNCTION public.heartbeat_gtm_job(UUID, TEXT, UUID, INTEGER) TO empiredb_app;
GRANT EXECUTE ON FUNCTION public.complete_gtm_job(UUID, TEXT, UUID, JSONB) TO empiredb_app;
GRANT EXECUTE ON FUNCTION public.fail_gtm_job(UUID, TEXT, UUID, TEXT, INTEGER, JSONB) TO empiredb_app;

COMMENT ON FUNCTION public.claim_next_gtm_job(TEXT, INTEGER) IS
    'Claims one approved queued GTM job with a bounded lease using SKIP LOCKED.';
COMMENT ON FUNCTION public.heartbeat_gtm_job(UUID, TEXT, UUID, INTEGER) IS
    'Renews a valid running GTM job lease.';
COMMENT ON FUNCTION public.complete_gtm_job(UUID, TEXT, UUID, JSONB) IS
    'Completes a GTM job only when worker and lease token match.';
COMMENT ON FUNCTION public.fail_gtm_job(UUID, TEXT, UUID, TEXT, INTEGER, JSONB) IS
    'Fails or requeues a GTM job according to bounded retry state.';
