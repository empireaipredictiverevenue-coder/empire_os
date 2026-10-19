"""V43 Bloom exact-confirmation negative controls, fixtures only."""
from datetime import datetime, timedelta, timezone
import json

import pytest

from empire_os.flagship_v43_novelty_shadow import review_v43_novelty_shadow

NOW = datetime(2026,10,19,19,tzinfo=timezone.utc)
KNOWN = "a"*64
NOVEL = "b"*64
ALSO_NOVEL = "c"*64


def fixture(key=NOVEL, **kwargs):
    item = {
        "source_digest_sha256": key,
        "source_observed_at": (NOW-timedelta(hours=1)).isoformat(),
        "bloom_maybe_seen": True,
        "source_rights_verified": False,
        "conditional_etag_state": "UNKNOWN",
        "classifier_label": "UNDETERMINED",
        "classifier_independently_validated": False,
    }
    item.update(kwargs)
    return item


def run(*sources, known=None):
    return review_v43_novelty_shadow(
        observations=list(sources),
        exact_known_source_digests=[KNOWN] if known is None else known,
        as_of=NOW,
    )


def test_bloom_positive_with_unknown_digest_is_not_silently_discarded():
    r=run(fixture())
    assert r["status"] == "SYNTHETIC_EVIDENCE_YIELD_SHADOW_ONLY"
    assert r["counts"]["not_known_research_candidates"] == 1
    assert r["counts"]["bloom_maybe_positive_without_exact_confirmation"] == 1
    assert r["counts"]["exact_known_reference"] == 0
    assert r["auto_dropping_new_sources"] is False
    assert r["source_rights_authenticated_by_shadow"] is False
    assert r["saved_crawl_costs_empirically_measured"] is False
    assert r["outbound_sent"] is False


def test_exact_known_digest_is_not_a_new_source():
    r=run(fixture(KNOWN))
    assert r["counts"]["exact_known_reference"] == 1
    assert r["counts"]["not_known_research_candidates"] == 0


def test_bloom_false_negative_is_detected_without_forging_novelty():
    r=run(fixture(KNOWN,bloom_maybe_seen=False))
    assert r["counts"]["bloom_false_negative_against_supplied_exact_inventory"] == 1
    assert r["counts"]["exact_known_reference"] == 1


def test_etag_not_modified_cannot_verify_rights_or_ground_truth():
    r=run(fixture(conditional_etag_state="NOT_MODIFIED",classifier_label="RELEVANT"))
    assert r["counts"]["conditional_etag_not_modified_observation"] == 1
    assert r["counts"]["source_rights_not_verified"] == 1
    assert r["counts"]["classifier_not_independently_validated"] == 1
    assert r["classifier_label_not_ground_truth"] is True


def test_no_source_details_or_identities_exported():
    r=run(fixture(NOVEL),fixture(ALSO_NOVEL,bloom_maybe_seen=False))
    serialized=json.dumps(r)
    assert NOVEL not in serialized
    assert ALSO_NOVEL not in serialized
    assert r["counts"]["not_known_research_candidates"] == 2
    assert r["customer_data_accessed"] is False


@pytest.mark.parametrize("change", [
    {"source_digest_sha256":"not-sha"},
    {"source_observed_at":"2026-10-19T18:00:00"},
    {"source_observed_at":(NOW+timedelta(minutes=1)).isoformat()},
    {"bloom_maybe_seen":"yes"},
    {"source_rights_verified":None},
    {"classifier_independently_validated":1},
    {"conditional_etag_state":"UNTRUSTED"},
    {"classifier_label":"CERTIFIED_BUYER"},
])
def test_bad_and_future_provenance_rejected_or_held(change):
    x=fixture(**change)
    if "source_observed_at" in change and "+" in str(change["source_observed_at"]):
        r=run(x)
        assert r["counts"]["source_timestamp_not_current"] == 1
    else:
        with pytest.raises(ValueError):
            run(x)


def test_duplicate_same_snapshot_digest_fails_closed():
    with pytest.raises(ValueError,match="repeated"):
        run(fixture(NOVEL),fixture(NOVEL))


def test_unknown_digest_inventory_fails_closed():
    with pytest.raises(ValueError):
        run(fixture(NOVEL),known=["this-is-a-url-not-a-digest"])


def test_out_of_bounds_batch_does_not_benchmark():
    with pytest.raises(ValueError,match="bounded"):
        run(*[fixture(hex(n)[2:].zfill(64)) for n in range(251)])


def test_empty_batch_does_not_claim_accuracy():
    r=run()
    assert r["observed_fixture_count"] == 0
    assert r["saved_crawl_costs_empirically_measured"] is False
    assert r["false_positive_rate_generalizes_to_production"] is False
