-- Second bounded Supabase exposure hardening slice.
-- Internal operational/control surfaces only. Staged: production apply gated.
BEGIN;

DO $$
DECLARE
  required_table text;
BEGIN
  FOREACH required_table IN ARRAY ARRAY[
    'public.agent_activity',
    'public.agent_config',
    'public.agent_roles',
    'public.agent_task_queue',
    'public.agent_baselines',
    'public.agent_improvements',
    'public.watcher_findings',
    'public.self_healer_log',
    'public.media_pipeline_runs',
    'public.enrichment_pipeline_runs',
    'public.business_actions_log',
    'public.business_recommendations'
  ]
  LOOP
    IF to_regclass(required_table) IS NULL THEN
      RAISE EXCEPTION
        'Operational hardening dependency missing: %',
        required_table;
    END IF;
  END LOOP;
END $$;

REVOKE ALL PRIVILEGES ON TABLE
  public.agent_activity,
  public.agent_config,
  public.agent_roles,
  public.agent_task_queue,
  public.agent_baselines,
  public.agent_improvements,
  public.watcher_findings,
  public.self_healer_log,
  public.media_pipeline_runs,
  public.enrichment_pipeline_runs,
  public.business_actions_log,
  public.business_recommendations
FROM anon, authenticated;

ALTER TABLE public.agent_activity ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_config ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_roles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_task_queue ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_baselines ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_improvements ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.watcher_findings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.self_healer_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.media_pipeline_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.enrichment_pipeline_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.business_actions_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.business_recommendations ENABLE ROW LEVEL SECURITY;

-- No anon/authenticated policies are created intentionally.
-- These are internal server/control-plane tables. service_role and table
-- owners retain their existing server-side authority.

COMMENT ON TABLE public.agent_task_queue IS
'Internal agent work queue; direct anon/authenticated Data API access revoked.';
COMMENT ON TABLE public.watcher_findings IS
'Internal watcher telemetry; direct anon/authenticated Data API access revoked.';
COMMENT ON TABLE public.self_healer_log IS
'Internal self-healing audit log; direct anon/authenticated Data API access revoked.';
COMMENT ON TABLE public.business_actions_log IS
'Internal business action audit surface; direct anon/authenticated Data API access revoked.';

COMMIT;
