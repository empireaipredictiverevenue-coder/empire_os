from datetime import datetime, timezone

from empire_os.buyer_network_research_rotation import (
    accepted_domain, choose_research_batch,
    make_research_summary, retain_recent_results,
)


NOW = datetime(2026, 10, 9, 20, tzinfo=timezone.utc).timestamp()


def fake_backlog(verify=12, watch=133):
    rows = [
        {"domain": f"v{i:03}.com", "status": "VERIFY_REQUIREMENTS", "score": 70-i}
        for i in range(verify)
    ] + [
        {"domain": f"w{i:03}.com", "status": "WATCH", "score": 55-i//5}
        for i in range(watch)
    ]
    rows.extend([
        {"domain": "empire-ai.co.uk", "status": "WATCH", "score": 999},
        {"domain": "yourdomain.com", "status": "VERIFY_REQUIREMENTS", "score": 999},
    ])
    return {"generated_at": "2026-10-09T20:00:00Z", "candidates": rows}


def test_research_145_entire_queue_rotates_in_bounded_batches():
    source = fake_backlog()
    ledger = {"domains": {}}
    probed = []
    for _ in range(20):
        batch, counts = choose_research_batch(
            source, ledger, now_epoch=NOW, limit=8,
        )
        assert len(batch) <= 8
        assert not set(x["domain"] for x in batch).intersection(probed)
        for item in batch:
            probed.append(item["domain"])
            ledger["domains"][item["domain"]] = {
                "last_attempt_epoch": NOW, "status": "EVIDENCE_INSUFFICIENT",
            }
        if len(probed) == 145:
            break
    assert len(probed) == 145
    assert len(set(probed)) == 145
    assert probed[:12] == [f"v{i:03}.com" for i in range(12)]
    assert probed[12].startswith("w")
    final, counts = choose_research_batch(source, ledger, now_epoch=NOW, limit=8)
    assert final == []
    assert counts["invalid"] == 2
    assert counts["cooldown"] == 145


def test_watch_eventually_runs_even_if_verify_has_high_scores():
    source = fake_backlog(verify=12, watch=133)
    ledger = {"domains": {"v000.com": {"last_attempt_epoch": NOW}}}
    batch, _ = choose_research_batch(source, ledger, now_epoch=NOW, limit=8)
    assert all(x["status"] == "VERIFY_REQUIREMENTS" for x in batch)
    assert "v000.com" not in [x["domain"] for x in batch]
    assert len(batch)==8


def test_cooldown_retries_are_bounded_and_do_not_require_manual_timer():
    source = fake_backlog(verify=1, watch=0)
    ledger = {"domains": {"v000.com": {"last_attempt_epoch": NOW}}}
    selected, _ = choose_research_batch(source, ledger, now_epoch=NOW+3600)
    assert selected == []
    due, _ = choose_research_batch(source, ledger, now_epoch=NOW+25*3600)
    assert len(due) == 1


def test_exclude_placeholder_owned_and_reserved_domains():
    for domain in (
        "yourdomain.com", "yoursite.com", "company.com", "insider.com", "o123.ingest.us.sentry.io", "empire-ai.co.uk", "example.com",
        "example.net", "company.local", "test.com", "127.0.0.1",
        "empire.buyer", "empire.predictive", "latest.json",
        "semrush.com", "ahrefs.com", "serpapi.com", "localfalcon.com",
    ):
        assert not accepted_domain(domain)
    for domain in ("px.com", "leadsmartinc.com", "callflowmarket.com"):
        assert accepted_domain(domain)


def test_results_deduplicated_and_expire_without_fabricating_revenue():
    old = [{"domain": "px.com", "observed_epoch": NOW-8*86400,
            "corroborated": True},
           {"domain": "leadsmartinc.com", "observed_epoch": NOW-100,
            "corroborated": True}]
    new = [{"domain": "leadsmartinc.com", "observed_epoch": NOW,
            "corroborated": False},
           {"domain": "callflowmarket.com", "observed_epoch": NOW,
            "corroborated": True},
           {"domain": "yourdomain.com", "observed_epoch": NOW,
            "corroborated": True}]
    result = retain_recent_results(old, new, now_epoch=NOW)
    assert [x["domain"] for x in result] == [
        "callflowmarket.com", "leadsmartinc.com",
    ]
    assert result[-1]["corroborated"] is False
    summary = make_research_summary(
        fake_backlog(), {"domains": {"v000.com": {"last_attempt_epoch": NOW}}},
        result,
    )
    assert summary["verify_attempted_count"] == 1
    assert summary["watch_attempted_count"] == 0
    assert summary["recent_first_party_corroborated_count"] == 1
    assert summary["direct_buyer_payment_proven"] is False
    assert summary["outbound_sent"] is False
    assert summary["execution_authority"] == "NONE"

def test_founder_excluded_domain_not_selected_from_stale_network_queue():
    assert not accepted_domain('callvox.pro')
    assert not accepted_domain('www.callvox.pro')
    queue = {'candidates': [
        {'domain': 'callvox.pro', 'status': 'VERIFY_REQUIREMENTS', 'score': 999},
        {'domain': 'polyares.com', 'status': 'WATCH', 'score': 1},
    ]}
    selected, counts = choose_research_batch(queue, {}, now_epoch=NOW)
    assert [x['domain'] for x in selected] == ['polyares.com']
    assert counts['invalid'] == 1
    fresh = retain_recent_results([], [
        {'domain': 'callvox.pro', 'observed_epoch': NOW, 'corroborated': True},
        {'domain': 'polyares.com', 'observed_epoch': NOW, 'corroborated': True},
    ], now_epoch=NOW)
    assert [x['domain'] for x in fresh] == ['polyares.com']


def test_existing_buyer_brain_reranks_eligible_verify_only_preserving_cooldown():
    queue = {'candidates':[
        {'domain':'genericbuyer.com','status':'VERIFY_REQUIREMENTS','score':90},
        {'domain':'roofbuyer.com','status':'VERIFY_REQUIREMENTS','score':10},
        {'domain':'anotherbuyer.com','status':'WATCH','score':100},
    ]}
    base,_=choose_research_batch(queue,{},now_epoch=NOW,limit=2)
    assert [r['domain'] for r in base] == ['genericbuyer.com','roofbuyer.com']
    priorities={'roofbuyer.com':120,'genericbuyer.com':4,'anotherbuyer.com':149}
    ranked,_=choose_research_batch(queue,{},now_epoch=NOW,limit=2,priority_hints=priorities)
    assert [r['domain'] for r in ranked] == ['roofbuyer.com','genericbuyer.com']
    ledger={'domains':{'roofbuyer.com':{'last_attempt_epoch':NOW}}}
    throttled,_=choose_research_batch(queue,ledger,now_epoch=NOW+3600,limit=2,
                                      priority_hints=priorities)
    assert 'roofbuyer.com' not in [r['domain'] for r in throttled]
    assert len(throttled)==2
    # Hints cannot admit excluded/non-public/suppressed companies.
    queue['candidates'].append(
        {'domain':'yourdomain.com','status':'VERIFY_REQUIREMENTS','score':999})
    selected,_=choose_research_batch(queue,{},now_epoch=NOW,limit=8,
                                      priority_hints={**priorities,'yourdomain.com':150})
    assert 'yourdomain.com' not in [r['domain'] for r in selected]
