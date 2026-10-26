"""Evidence effectiveness is descriptive, not buyer acceptance or causality."""
from datetime import datetime, timedelta, timezone

from empire_os.buyer_scout_effectiveness import research_effectiveness, SCHEMA

NOW = datetime(2026, 10, 26, 18, tzinfo=timezone.utc)


def qualification(*, role=False, gaps=None):
    return {
        "schema_version": "empire.buyer_qualification_actions.v1",
        "mode": "OBSERVE", "execution_authority": "none",
        "outbound_sent": False, "outbound_enabled": False,
        "generated_at": NOW.isoformat(),
        "targets": [{"domain": "genuinecompany.com",
                     "site_corroborated_buyer_role": role,
                     "missing_evidence": gaps or [],
                     "active_demand_sector_research_fit": {"state": "NO_SECTOR_GAP_MATCH_OBSERVED"}}],
    }


def ledger(epoch=0, status="EVIDENCE_INSUFFICIENT"):
    return {"schema_version": "empire.buyer_network_research_ledger.v1",
            "mode": "OBSERVE", "domains": {
                "genuinecompany.com": {"last_attempt_epoch": epoch, "status": status}}}


def website(*, epoch=None, proven=True):
    epoch = epoch or NOW.timestamp()
    return {"schema_version": "buyer-direct-site-verification-v1",
            "authority": "OBSERVE",
            "governance": {key: False for key in ("outbound", "forms", "logins",
                "db_write", "traffic_activation", "commercial_terms", "funds")},
            "results": [{"domain": "genuinecompany.com", "observed_epoch": epoch,
                         "corroborated": proven, "buyer_role": proven,
                         "pages_successful": 2, "positive_category_count": 4,
                         "evidence": {"negative_program": False}}]}


def calculate(before, after, prior=None, start=0, end=None, site=None):
    return research_effectiveness(
        before, after, ledger(start), ledger(end or NOW.timestamp(),
        "CORROBORATED_FIRST_PARTY"), site or website(), prior or {},
        {}, {}, now=NOW,
    )


def test_real_site_improvement_is_observed_without_inferred_commercial_success():
    r=calculate(qualification(gaps=["verify_active_buyer_demand"]),
                qualification(role=True), start=NOW.timestamp()-100)
    assert r["schema_version"] == SCHEMA
    assert r["status"] == "MEASURED"
    assert r["attempted_site_domains_with_joined_receipts"] == 1
    assert r["company_research_evidence_improvement_count"] == 1
    assert r["improvements"][0]["removed_gap_count"] == 1
    for field in ("causality_proven","commercial_buyer_accepted",
                  "buyer_zip_capacity_verified","outbound_sent","database_writes",
                  "payment_authorized"):
        assert r[field] is False


def test_repeated_insufficient_evidence_receives_bounded_priority_penalty():
    prior={}
    for i in range(3):
        r=calculate(qualification(), qualification(), prior=prior,
                    start=NOW.timestamp()-100, end=NOW.timestamp())
        prior=r
    assert r["company_research_evidence_improvement_count"] == 0
    assert r["research_deprioritization_hints"]["genuinecompany.com"] == 60
    assert r["penalties_are_advisory_not_eligibility"] is True


def test_unchanged_ledger_or_conflicting_site_evidence_never_claims_attempt():
    same=calculate(qualification(), qualification(),
                   start=NOW.timestamp(), end=NOW.timestamp())
    assert same["attempted_site_domains_with_joined_receipts"] == 0
    mismatched=calculate(qualification(), qualification(),
                         start=NOW.timestamp()-100, site=website(epoch=NOW.timestamp()-120))
    assert mismatched["attempted_site_domains_with_joined_receipts"] == 0
    bad=calculate({}, qualification(), start=NOW.timestamp()-100)
    assert bad["status"] == "UNMEASURABLE_MISSING_OR_UNSAFE_SOURCE"
    assert bad["company_research_evidence_improvement_count"] == 0


def test_fresh_public_lane_and_main_scout_are_reported_separately():
    public={"schema_version":"empire.buyer_public_research_seeds.v1",
            "generated_at":NOW.isoformat(),"mode":"OBSERVE","outbound_sent":False,
            "fresh_search_result_status":"DEFERRED_LOW_YIELD_BACKOFF",
            "fresh_search_domain_count":0,
            "source_recovery":{"repeat_search_deferred":True}}
    scout={"generated_at":NOW.isoformat(),"mode":"OBSERVE",
           "outbound_sent":False,"search_domain_count":16}
    r=research_effectiveness(qualification(), qualification(), ledger(0),
            ledger(0), website(), {}, public, scout, now=NOW)
    assert r["public_seed_lane"]["repeat_search_deferred"] is True
    assert r["original_scout"]["search_domains"] == 16
    assert r["source_recovery_route"] == "ORIGINAL_SITE_QUEUE_AND_OFFICIAL_FIRST_PARTY_SEEDS"
