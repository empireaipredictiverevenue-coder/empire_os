"""Draft checks only: NOT a PostgreSQL DDL execution or DBA release proof."""
from pathlib import Path
import re

DRAFT=(
    Path(__file__).resolve().parents[1]/
    "docs/commercial/sql/EXCHANGE_NATIVE_SEAT_TABLES_REVIEW_ONLY_NOT_APPROVED.sql"
)

def test_proposed_tables_not_discovered_as_auto_migration():
    assert "/docs/commercial/sql/" in str(DRAFT)
    assert "migrations/empiredb/" not in str(DRAFT)
    sql=DRAFT.read_text(encoding="utf-8")
    assert "NOT APPROVED FOR PRODUCTION" in sql
    assert sql.count("CREATE TABLE public.exchange_seat_")==2
    assert sql.count("ENABLE ROW LEVEL SECURITY")==2
    assert sql.count("FORCE ROW LEVEL SECURITY")==2
    assert sql.count("REVOKE ALL ON public.exchange_seat_")==2
    assert "EXCHANGE_SEAT_DRAFT_UNEXPECTED_ACL_OR_RLS_DRIFT" in sql
    assert "FROM pg_catalog.aclexplode(" in sql
    assert "acl.grantee <> c.relowner" in sql
    assert "EXCHANGE_SEAT_DRAFT_WRONG_DB_ROLE" in sql
    assert re.search(r"BEGIN;\s*SET LOCAL statement_timeout",sql)
    assert sql.rstrip().endswith("DO NOT INVOKE IN PRODUCTION. Reconcile live catalog + approve later version.")
    assert re.search(r"\bCOMMIT;",sql)


def test_constraints_cover_native_bsc_replay_and_recurring_payments():
    sql=DRAFT.read_text(encoding="utf-8")
    for clause in (
        "UNIQUE (membership_id,period_index)",
        "UNIQUE (membership_id,period_start)",
        "payment_request_id uuid UNIQUE",
        "payment_evidence_id uuid UNIQUE",
        "invoice_order_id uuid UNIQUE",
        "REFERENCES public.bsc_payment_evidence(id)",
        "REFERENCES public.bsc_payment_requests(id)",
        "REFERENCES public.fulfilment_orders(id)",
        "CHECK (period_end > period_start)",
        "contract_state IN ('proposed','accepted','suspended','cancelled')",
        "cycle_state IN ('pending','paid_receipt_review','held','refunded','reversed')",
        "commercial_terms_sha256 text NOT NULL",
        "source_kind='native_exchange_seat_monthly'",
    ):
        assert clause in sql,clause


def test_no_financial_or_app_authority_granted():
    sql=DRAFT.read_text(encoding="utf-8")
    stripped=re.sub(r"--[^\n]*","",sql)
    for forbidden in (
        "CREATE ROLE ","CREATE USER ","GRANT ","SECURITY DEFINER",
        "INSERT INTO ","UPDATE public.","DELETE FROM ","CREATE POLICY ",
        "TRUNCATE ","DROP TABLE ","ALTER ROLE ","BYPASSRLS",
    ):
        assert forbidden not in stripped,forbidden
    assert "CREATE TABLE public.buyer_subscriptions" not in stripped
