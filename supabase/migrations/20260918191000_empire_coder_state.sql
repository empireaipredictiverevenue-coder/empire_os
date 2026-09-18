-- Empire Coder durable engineering-task state.
-- Staged only: no production migration or credential activation here.
BEGIN;

CREATE TABLE IF NOT EXISTS public.coder_tasks (
  id text PRIMARY KEY,
  objective text NOT NULL CHECK (length(btrim(objective)) > 0),
  workspace text NOT NULL,
  branch text,
  base_commit text,
  blueprint_path text NOT NULL DEFAULT 'docs/BLUEPRINT_V6.md',
  permission_profile text NOT NULL DEFAULT 'observe_developer',
  execution_mode text NOT NULL DEFAULT 'OBSERVE'
    CHECK (execution_mode = 'OBSERVE'),
  status text NOT NULL,
  phase text NOT NULL,
  model_route jsonb,
  plan jsonb NOT NULL DEFAULT '[]'::jsonb,
  compact_context jsonb NOT NULL DEFAULT '{}'::jsonb,
  pending_approval jsonb NOT NULL DEFAULT '[]'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.coder_steps (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  task_id text NOT NULL REFERENCES public.coder_tasks(id) ON DELETE CASCADE,
  step_key text NOT NULL,
  ordinal integer NOT NULL CHECK (ordinal >= 0),
  phase text NOT NULL,
  status text NOT NULL,
  objective text,
  result text,
  depends_on jsonb NOT NULL DEFAULT '[]'::jsonb,
  files jsonb NOT NULL DEFAULT '[]'::jsonb,
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (task_id, step_key)
);

CREATE TABLE IF NOT EXISTS public.coder_tool_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  task_id text NOT NULL REFERENCES public.coder_tasks(id) ON DELETE CASCADE,
  tool text NOT NULL,
  arguments_summary text NOT NULL,
  policy_decision text NOT NULL,
  exit_status integer,
  mutation_occurred boolean NOT NULL DEFAULT false,
  timed_out boolean NOT NULL DEFAULT false,
  output_excerpt text,
  error_excerpt text,
  started_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz
);

CREATE TABLE IF NOT EXISTS public.coder_findings (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  task_id text NOT NULL REFERENCES public.coder_tasks(id) ON DELETE CASCADE,
  kind text NOT NULL,
  severity text NOT NULL,
  message text NOT NULL,
  file_path text,
  line integer,
  evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.coder_patches (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  task_id text NOT NULL REFERENCES public.coder_tasks(id) ON DELETE CASCADE,
  file_path text NOT NULL,
  operation text NOT NULL,
  before_sha256 text,
  after_sha256 text,
  checkpoint_ref text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.coder_proposals (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  task_id text NOT NULL REFERENCES public.coder_tasks(id) ON DELETE CASCADE,
  provider text NOT NULL,
  model text NOT NULL,
  stage text NOT NULL CHECK (
    stage IN ('DRAFT','CANDIDATES_READY','CRITIQUED','REFINED')
  ),
  draft text NOT NULL,
  candidate_drafts jsonb NOT NULL DEFAULT '[]'::jsonb
    CHECK (jsonb_typeof(candidate_drafts) = 'array'),
  critique text,
  refined text,
  revision_count integer NOT NULL DEFAULT 0 CHECK (revision_count >= 0),
  actionable boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (
    actionable = false
    OR (
      stage = 'REFINED'
      AND revision_count >= 1
      AND jsonb_array_length(candidate_drafts) >= 2
      AND critique IS NOT NULL
      AND length(btrim(critique)) > 0
      AND refined IS NOT NULL
      AND length(btrim(refined)) > 0
      AND refined IS DISTINCT FROM candidate_drafts->>0
    )
  )
);

CREATE TABLE IF NOT EXISTS public.coder_command_proposals (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  task_id text NOT NULL REFERENCES public.coder_tasks(id) ON DELETE CASCADE,
  provider text NOT NULL,
  model text NOT NULL,
  candidate_texts jsonb NOT NULL
    CHECK (
      jsonb_typeof(candidate_texts) = 'array'
      AND jsonb_array_length(candidate_texts) >= 2
    ),
  critique text NOT NULL CHECK (length(btrim(critique)) > 0),
  synthesized_text text NOT NULL CHECK (length(btrim(synthesized_text)) > 0),
  argv jsonb NOT NULL
    CHECK (
      jsonb_typeof(argv) = 'array'
      AND jsonb_array_length(argv) >= 1
    ),
  policy_decision text NOT NULL
    CHECK (policy_decision IN ('allow','require_approval','deny')),
  eligible boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (
    eligible = false
    OR (
      policy_decision IN ('allow','require_approval')
      AND jsonb_array_length(candidate_texts) >= 2
      AND jsonb_array_length(argv) >= 1
    )
  )
);

CREATE TABLE IF NOT EXISTS public.coder_context_snapshots (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  task_id text NOT NULL REFERENCES public.coder_tasks(id) ON DELETE CASCADE,
  version integer NOT NULL CHECK (version >= 1),
  trigger text NOT NULL,
  compact_context jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (task_id, version)
);

CREATE TABLE IF NOT EXISTS public.coder_knowledge_sources (
  path text PRIMARY KEY,
  kind text NOT NULL
    CHECK (kind IN ('canonical','curated_skill','legacy_prompt')),
  status text NOT NULL
    CHECK (status IN ('ACTIVE','REVIEW','QUARANTINED')),
  authority integer NOT NULL CHECK (authority BETWEEN 0 AND 100),
  sha256 text NOT NULL,
  bytes bigint NOT NULL CHECK (bytes >= 0),
  flags jsonb NOT NULL DEFAULT '[]'::jsonb
    CHECK (jsonb_typeof(flags) = 'array'),
  duplicate_of text,
  last_scanned_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.coder_verifications (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  task_id text NOT NULL REFERENCES public.coder_tasks(id) ON DELETE CASCADE,
  verdict text NOT NULL CHECK (
    verdict IN ('PASS','FAIL','PASS_WITH_WARNINGS')
  ),
  checks jsonb NOT NULL DEFAULT '[]'::jsonb,
  reasons jsonb NOT NULL DEFAULT '[]'::jsonb,
  warnings jsonb NOT NULL DEFAULT '[]'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_coder_tasks_status
  ON public.coder_tasks(status, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_coder_steps_task
  ON public.coder_steps(task_id, ordinal);
CREATE INDEX IF NOT EXISTS idx_coder_tool_runs_task
  ON public.coder_tool_runs(task_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_coder_findings_task
  ON public.coder_findings(task_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_coder_patches_task
  ON public.coder_patches(task_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_coder_proposals_task
  ON public.coder_proposals(task_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_coder_command_proposals_task
  ON public.coder_command_proposals(task_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_coder_context_snapshots_task
  ON public.coder_context_snapshots(task_id, version DESC);
CREATE INDEX IF NOT EXISTS idx_coder_knowledge_sources_status
  ON public.coder_knowledge_sources(status, authority DESC);
CREATE INDEX IF NOT EXISTS idx_coder_verifications_task
  ON public.coder_verifications(task_id, created_at DESC);

ALTER TABLE public.coder_tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.coder_steps ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.coder_tool_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.coder_findings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.coder_patches ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.coder_proposals ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.coder_command_proposals ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.coder_context_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.coder_knowledge_sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.coder_verifications ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_roles WHERE rolname='empire_coder_state'
  ) THEN
    CREATE ROLE empire_coder_state
      NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
      NOREPLICATION NOBYPASSRLS;
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_roles WHERE rolname='empire_coder_state_login'
  ) THEN
    CREATE ROLE empire_coder_state_login
      LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
      NOREPLICATION NOBYPASSRLS CONNECTION LIMIT 3;
  END IF;
END $$;

ALTER ROLE empire_coder_state_login PASSWORD NULL;
ALTER ROLE empire_coder_state_login SET statement_timeout='15s';
ALTER ROLE empire_coder_state_login
  SET idle_in_transaction_session_timeout='30s';

GRANT USAGE ON SCHEMA public TO empire_coder_state;
GRANT empire_coder_state TO empire_coder_state_login;

REVOKE ALL ON
  public.coder_tasks,
  public.coder_steps,
  public.coder_tool_runs,
  public.coder_findings,
  public.coder_patches,
  public.coder_proposals,
  public.coder_command_proposals,
  public.coder_context_snapshots,
  public.coder_knowledge_sources,
  public.coder_verifications
FROM PUBLIC, anon, authenticated, service_role;

GRANT SELECT, INSERT, UPDATE ON
  public.coder_tasks,
  public.coder_steps,
  public.coder_knowledge_sources
TO empire_coder_state;

GRANT SELECT, INSERT ON
  public.coder_tool_runs,
  public.coder_findings,
  public.coder_patches,
  public.coder_proposals,
  public.coder_command_proposals,
  public.coder_context_snapshots,
  public.coder_verifications
TO empire_coder_state;

CREATE POLICY coder_tasks_state_role
  ON public.coder_tasks
  FOR ALL TO empire_coder_state
  USING (true) WITH CHECK (true);

CREATE POLICY coder_steps_state_role
  ON public.coder_steps
  FOR ALL TO empire_coder_state
  USING (true) WITH CHECK (true);

CREATE POLICY coder_tool_runs_state_role
  ON public.coder_tool_runs
  FOR SELECT TO empire_coder_state
  USING (true);
CREATE POLICY coder_tool_runs_insert_role
  ON public.coder_tool_runs
  FOR INSERT TO empire_coder_state
  WITH CHECK (true);

CREATE POLICY coder_findings_state_role
  ON public.coder_findings
  FOR SELECT TO empire_coder_state
  USING (true);
CREATE POLICY coder_findings_insert_role
  ON public.coder_findings
  FOR INSERT TO empire_coder_state
  WITH CHECK (true);

CREATE POLICY coder_patches_state_role
  ON public.coder_patches
  FOR SELECT TO empire_coder_state
  USING (true);
CREATE POLICY coder_patches_insert_role
  ON public.coder_patches
  FOR INSERT TO empire_coder_state
  WITH CHECK (true);

CREATE POLICY coder_proposals_state_role
  ON public.coder_proposals
  FOR SELECT TO empire_coder_state
  USING (true);
CREATE POLICY coder_proposals_insert_role
  ON public.coder_proposals
  FOR INSERT TO empire_coder_state
  WITH CHECK (true);

CREATE POLICY coder_command_proposals_state_role
  ON public.coder_command_proposals
  FOR SELECT TO empire_coder_state
  USING (true);
CREATE POLICY coder_command_proposals_insert_role
  ON public.coder_command_proposals
  FOR INSERT TO empire_coder_state
  WITH CHECK (true);

CREATE POLICY coder_context_snapshots_state_role
  ON public.coder_context_snapshots
  FOR SELECT TO empire_coder_state
  USING (true);
CREATE POLICY coder_context_snapshots_insert_role
  ON public.coder_context_snapshots
  FOR INSERT TO empire_coder_state
  WITH CHECK (true);

CREATE POLICY coder_knowledge_sources_state_role
  ON public.coder_knowledge_sources
  FOR ALL TO empire_coder_state
  USING (true) WITH CHECK (true);

CREATE POLICY coder_verifications_state_role
  ON public.coder_verifications
  FOR SELECT TO empire_coder_state
  USING (true);
CREATE POLICY coder_verifications_insert_role
  ON public.coder_verifications
  FOR INSERT TO empire_coder_state
  WITH CHECK (true);

COMMENT ON TABLE public.coder_tasks IS
'Empire Coder engineering task state only; no commercial execution authority.';
COMMENT ON TABLE public.coder_tool_runs IS
'Redacted structured engineering tool history; never store credentials/secrets.';
COMMENT ON TABLE public.coder_context_snapshots IS
'Append-only compact recovery context for long-running Empire Coder tasks.';
COMMENT ON TABLE public.coder_knowledge_sources IS
'Knowledge-garden metadata only; original source content remains in the repository.';
COMMENT ON TABLE public.coder_command_proposals IS
'Best-of-N command candidates, critique, synthesized argv and policy decision.';
COMMENT ON ROLE empire_coder_state IS
'Least-privilege engineering-state role for Empire Coder only.';
COMMENT ON ROLE empire_coder_state_login IS
'Passwordless staged login for Empire Coder state; provision out of band.';

COMMIT;
