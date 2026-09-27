from pathlib import Path


MIGRATION = Path(
    "supabase/migrations/"
    "20260926190506_fix_buyer_scout_contact_provenance.sql"
)


def test_promotion_rpc_preserves_observed_contact_provenance():
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "contact_source text;" in sql
    assert "first_party_person ->> 'source'" in sql
    assert "first_party_person ->> 'identity_source'" in sql
    assert "'first_party_site'" in sql
    assert "THEN contact_source ELSE NULL END" in sql
