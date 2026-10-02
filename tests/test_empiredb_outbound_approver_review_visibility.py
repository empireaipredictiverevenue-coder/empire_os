"""Executable regression for outbound approver review visibility under RLS."""
from pathlib import Path

from test_empiredb_materializer_bootstrap import execute


MIGRATION = Path(
    "migrations/empiredb/030_outbound_approver_review_visibility.sql"
)


SCHEMA = r"""
CREATE ROLE empiredb_migrator NOLOGIN;
CREATE ROLE empire_outbound_approver NOLOGIN NOINHERIT;
CREATE ROLE empire_outbound_approver_login LOGIN NOINHERIT;
GRANT empire_outbound_approver TO empire_outbound_approver_login;

GRANT USAGE, CREATE ON SCHEMA public TO empiredb_migrator;
SET ROLE empiredb_migrator;

CREATE TABLE public.buyer_candidate_reviews(
  id uuid PRIMARY KEY,
  status text NOT NULL,
  reviewed_at timestamptz,
  contact_name text,
  contact_title text,
  contact_email text
);
ALTER TABLE public.buyer_candidate_reviews ENABLE ROW LEVEL SECURITY;

GRANT USAGE ON SCHEMA public TO empire_outbound_approver;
GRANT SELECT ON public.buyer_candidate_reviews TO empire_outbound_approver;

INSERT INTO public.buyer_candidate_reviews(
  id,status,reviewed_at,contact_name,contact_title,contact_email
) VALUES (
  '10000000-0000-0000-0000-000000000001',
  'approved',
  pg_catalog.clock_timestamp(),
  'Bobby Hernandez',
  'owner',
  'bobby@example.test'
);

RESET ROLE;
"""


def test_approver_cannot_see_review_before_policy(execute):
    execute("postgres", "CREATE DATABASE empiredb;")
    execute("empiredb", SCHEMA)
    output = execute(
        "empiredb",
        """
SET ROLE empire_outbound_approver;
SELECT count(*) FROM public.buyer_candidate_reviews;
RESET ROLE;
""",
    )
    assert "0" in output


def test_migration_restores_only_read_visibility(execute):
    execute("postgres", "CREATE DATABASE empiredb;")
    execute("empiredb", SCHEMA)
    migration = MIGRATION.read_text()
    execute("empiredb", migration)
    execute("empiredb", migration)

    output = execute(
        "empiredb",
        """
SET ROLE empire_outbound_approver;
SELECT count(*)
FROM public.buyer_candidate_reviews
WHERE status='approved'
  AND reviewed_at >= pg_catalog.clock_timestamp()-interval '7 days';
RESET ROLE;
""",
    )
    assert "1" in output

    execute(
        "empiredb",
        """
SET ROLE empire_outbound_approver;
UPDATE public.buyer_candidate_reviews
SET status='rejected'
WHERE id='10000000-0000-0000-0000-000000000001';
""",
        expected_error="permission denied for table buyer_candidate_reviews",
    )

    execute(
        "empiredb",
        """
SET ROLE empire_outbound_approver;
DELETE FROM public.buyer_candidate_reviews
WHERE id='10000000-0000-0000-0000-000000000001';
""",
        expected_error="permission denied for table buyer_candidate_reviews",
    )


def test_policy_is_select_only_for_bounded_approver():
    text = MIGRATION.read_text().lower()
    assert "for select" in text
    assert "to empire_outbound_approver" in text
    assert "using (true)" in text
    assert "grant update" not in text
    assert "grant insert" not in text
    assert "grant delete" not in text
    assert "auto_approve_outbound_intent" not in text
    assert "daily_cap" not in text
