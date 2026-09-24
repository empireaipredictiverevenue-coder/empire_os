from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase/migrations/"
    "20260924140851_refresh_pending_buyer_candidate_review_rpc.sql"
)


def test_pending_review_refresh_rpc_keeps_table_write_boundary_narrow():
    text = MIGRATION.read_text()

    assert "refresh_pending_buyer_candidate_review" in text
    assert "security definer" in text.lower()
    assert "set search_path = ''" in text.lower()
    assert "r.status <> 'pending'" in text
    assert "and status = 'pending'" in text
    assert "grant execute" in text.lower()
    assert "to service_role" in text.lower()
    assert "from public, anon, authenticated" in text.lower()
    assert "grant update" not in text.lower()
    assert "approve" not in text.lower().split("comment on function")[0]
    assert "outbound_intents" not in text
    assert "payment" not in text.lower().split("comment on function")[0]


def test_contact_worker_uses_rpc_instead_of_direct_table_patch():
    text = (
        ROOT / "empire_os/enterprise_contact_intelligence.py"
    ).read_text()

    assert (
        "/rest/v1/rpc/refresh_pending_buyer_candidate_review"
        in text
    )
    assert (
        'request,\n        "PATCH",\n'
        '        f"/rest/v1/buyer_candidate_reviews'
        not in text
    )
