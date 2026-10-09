from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def migration_text():
    matches = sorted(
        (
            ROOT
            / "migrations"
            / "empiredb"
        ).glob(
            "*_buyer_scout_candidate_to_prospect.sql"
        )
    )

    assert len(matches) == 1

    return matches[0].read_text(
        encoding="utf-8"
    ).lower()


def test_promotion_rpc_has_required_internal_gates():
    text = migration_text()

    assert (
        "promote_buyer_scout_candidate_to_prospect"
        in text
    )

    assert "review_ready" in text
    assert "first_party_people" in text
    assert "mx_verified" in text
    assert "email_directly_bound_to_person" in text
    assert "buyer_scout_domain:" in text
    assert "buy_signal_score" in text
    assert "'unknown_null'" in text


def test_promotion_rpc_does_not_create_external_commercial_state():
    text = migration_text()

    forbidden = (
        "insert into public.buyers",
        "insert into public.buyer_candidate_reviews",
        "insert into public.outbound_intents",
        "insert into public.outbound_events",
        "insert into public.fulfilment_orders",
        "insert into public.payment",
    )

    for token in forbidden:
        assert token not in text
