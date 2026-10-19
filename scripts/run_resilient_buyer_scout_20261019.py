"""Bounded buyer-source recovery when public search engines rate-limit.

Consumes the already-reviewed Buyer Network shortlist, reuses the EXISTING
Scout domain validation, first-party probing, scoring and output schema.
No search engine calls, CRM writes, contact discovery by inference or sending.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from empire_os.buyer_acquisition_scout import refresh_buyer_scout
from empire_os.leadgen_contact_history_bridge import (
    DOMAIN, TECHNICAL_HOSTS, build_contact_history_review,
)
from empire_os.buyer_scout_probe_cooldown import (
    load_probe_history, merge_observed_probes, save_probe_history,
)
from empire_os.buyer_scout_commercial_awareness import review_buyer_scout_awareness
from empire_os.buyer_scout_economic_intelligence import build_buyer_economic_gap_review

DEFAULT_ROOT = Path("/srv/empire_os")
SOURCE = "runtime/buyer_network_intelligence/founder_qualification_actions_latest.json"
PROBE_CACHE = "runtime/buyer_acquisition/resilient/research_cooldown_latest.json"
LAST_SCOUT = "runtime/buyer_acquisition/scout_latest.json"
RELATIONSHIPS = "runtime/buyer_network_intelligence/commercial_relationship_registry_latest.json"


def reviewed_seed_records(snapshot: dict, *, limit: int = 8,
                          rotation: int = 0,
                          recently_probed_domains: set[str] | None = None,
                          existing_relationship_domains: set[str] | None = None) -> list[dict]:
    if (snapshot.get("schema_version") != "empire.buyer_qualification_actions.v1"
            or snapshot.get("mode") != "OBSERVE"
            or snapshot.get("outbound_enabled") is not False
            or snapshot.get("outbound_sent") is not False):
        raise ValueError("buyer_research_contract_invalid")
    targets = snapshot.get("targets")
    if not isinstance(targets, list) or len(targets) > 100:
        raise ValueError("buyer_seed_population_invalid")
    domains = set()
    selected = []
    for item in targets:
        if not isinstance(item, dict) or item.get("outbound_authorized") is not False:
            raise ValueError("untrusted_existing_buyer_seed")
        domain = item.get("domain")
        if (not isinstance(domain, str) or not DOMAIN.fullmatch(domain)
                or domain.endswith(TECHNICAL_HOSTS) or domain in domains
                or domain in (recently_probed_domains or set())
                or domain in (existing_relationship_domains or set())):
            continue
        # This source's buyer-role assessment is research only, not approval.
        urls = item.get("existing_first_party_source_urls")
        refs = []
        if isinstance(urls, list):
            for raw in urls[:10]:
                if not isinstance(raw, str) or len(raw) > 850:
                    continue
                try:
                    u = urlsplit(raw)
                    if (u.scheme == "https" and not u.username and not u.password
                            and u.port is None
                            and u.hostname in (domain, "www." + domain)):
                        refs.append(raw)
                except ValueError:
                    continue
        selected.append({
            "website": "https://" + domain + "/",
            "domain": domain,
            "target_buyer_pools": ["direct_demand_buyers"],
            "source_refs": refs,
            "source_queries": [],
        })
        domains.add(domain)
    if not selected:
        return []
    # Rotate across all eligible founder-reviewed domains. A half-hour slot
    # changes the start offset, so the recovery does not probe the same
    # eight companies indefinitely while blocked search engines recover.
    if type(rotation) is not int or rotation < 0:
        raise ValueError("invalid_seed_rotation")
    window = (rotation % ((len(selected) + limit - 1) // limit)) * limit
    return (selected[window:] + selected[:window])[:limit]


def economics_only_summary(scout: dict, actions: dict, registry: dict, *, now: datetime) -> dict:
    """Never fail or authorise the Scout because an economic source is missing."""
    try:
        awareness = review_buyer_scout_awareness(scout, actions, registry, as_of=now)
        board = build_buyer_economic_gap_review(awareness, registry, as_of=now)
        return {
            "state": "READ_ONLY_ECONOMIC_GAP_BOARD",
            "existing_partner_pilots_reviewed": board["partner_pilots_reviewed"],
            "partner_buyboxes_missing": board["partner_pilots_without_verified_buybox"],
            "partner_payment_terms_missing": board["partner_pilots_without_verified_payable_terms"],
            "scout_domains_triaged": board["scout_domains_triaged"],
            "verified_paying_buyer_capacity": 0,
            "outbound_authorized": False,
        }
    except (ValueError, TypeError, KeyError):
        return {"state": "HOLD_ECONOMIC_REVIEW_SOURCE",
                "verified_paying_buyer_capacity": 0,
                "outbound_authorized": False}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run-observe", action="store_true", required=True)
    p.add_argument("--repo-root", type=Path, default=DEFAULT_ROOT)
    p.add_argument("--max-probes", type=int, default=4)
    p.add_argument("--max-seeds", type=int, default=8)
    args = p.parse_args(argv)
    # Never replace a still-running canonical Buyer Scout cycle. This fallback
    # only fills a failed/idle discovery window; its output is research-only.
    primary = subprocess.run(
        ["systemctl", "is-active", "empire-buyer-acquisition-scout.service"],
        check=False, capture_output=True, text=True, timeout=6,
    )
    if primary.stdout.strip() in ("active", "activating"):
        print(json.dumps({"schema_version": "empire.buyer_scout_resilient_recovery.v1",
                          "state": "PRIMARY_SCOUT_RUNNING_SKIPPED",
                          "canonical_empiredb_writes": False,
                          "outbound_sent": False, "execution_authority": "none"}))
        return 0
    if not 1 <= args.max_probes <= 6 or not 1 <= args.max_seeds <= 12:
        raise SystemExit("bounded_scout_limits_required")
    source = args.repo_root / SOURCE
    if source.is_symlink() or not source.is_file() or source.stat().st_size > 700_000:
        raise SystemExit("buyer_seed_snapshot_unavailable")
    data = json.loads(source.read_text(encoding="utf-8"))
    observed = datetime.fromisoformat(str(data.get("generated_at") or "").replace("Z", "+00:00"))
    if observed.tzinfo is None:
        raise SystemExit("buyer_seed_snapshot_timezone_missing")
    age_seconds = (datetime.now(timezone.utc) - observed).total_seconds()
    if age_seconds < -300 or age_seconds > 6 * 3600:
        raise SystemExit("buyer_seed_snapshot_stale")
    now = datetime.now(timezone.utc)
    memory_file = args.repo_root / PROBE_CACHE
    recent = load_probe_history(memory_file, now=now)
    # Bootstrap a previous successful first-party probe without re-probing.
    # This is a snapshot from the EXISTING Scout, not a new search/scan.
    prior_path = args.repo_root / LAST_SCOUT
    if prior_path.is_file() and not prior_path.is_symlink() and prior_path.stat().st_size <= 2_500_000:
        prior = json.loads(prior_path.read_text(encoding="utf-8"))
        observed_at = datetime.fromisoformat(str(prior.get("generated_at") or "").replace("Z", "+00:00"))
        if (observed_at.tzinfo is not None
                and 0 <= (now-observed_at).total_seconds() <= 24*3600):
            recent = merge_observed_probes(recent, prior, now=now)
    relpath = args.repo_root / RELATIONSHIPS
    if (relpath.is_symlink() or not relpath.is_file()
            or relpath.stat().st_size > 2_500_000):
        raise SystemExit("existing_relationship_registry_required")
    registry = json.loads(relpath.read_text(encoding="utf-8"))
    all_target_domains = sorted({str(row.get("domain"))
        for row in data.get("targets", []) if isinstance(row, dict)
        and isinstance(row.get("domain"), str)
        and DOMAIN.fullmatch(row["domain"])})
    history_review = build_contact_history_review(registry, all_target_domains, now=now)
    already_engaged = {domain for domain, result in history_review["by_domain"].items()
        if result["contact_state"] in ("DO_NOT_PURSUE", "EXISTING_THREAD_REVIEW",
                                       "NON_BUYER_TECHNICAL_HOST")}
    # Bounce evidence is a permanent research hold until CRM verifies a
    # different permitted contact route; never accidentally re-recruit.
    for relationship in registry["relationships"]:
        if relationship.get("bounced_addresses"):
            already_engaged.update(d for d in relationship.get("identity_domains", [])
                                   if isinstance(d, str) and DOMAIN.fullmatch(d))
    slot = int(now.timestamp() // 1800)
    seeds = reviewed_seed_records(
        data, limit=args.max_seeds, rotation=slot,
        recently_probed_domains=set(recent),
        existing_relationship_domains=already_engaged,
    )
    if not seeds:
        save_probe_history(memory_file, recent)
        print(json.dumps({
            "schema_version": "empire.buyer_scout_resilient_recovery.v1",
            "state": "COOLDOWN_NO_UNPROBED_RESEARCH_DOMAINS",
            "mode": "OBSERVE", "reviewed_seed_count": 0,
            "recent_first_party_domain_count": len(recent),
            "existing_relationship_domains_excluded": len(already_engaged),
            "first_party_probes_attempted": 0,
            "canonical_empiredb_writes": False,
            "outbound_sent": False, "execution_authority": "none",
        }, sort_keys=True))
        return 0
    out = refresh_buyer_scout(
        args.repo_root,
        max_queries=4,
        results_per_query=3,
        max_domains=12,
        max_probes=args.max_probes,
        canonical_seed_records=[],
        research_seed_records=seeds,
        search_enabled=False,
        low_yield_canonical_limit=0,
    )
    if out.get("schema_version") != "empire.buyer_acquisition_scout.v1":
        raise SystemExit("untrusted_scout_result")
    save_probe_history(memory_file, merge_observed_probes(recent, out, now=datetime.now(timezone.utc)))
    economics = economics_only_summary(out, data, registry, now=datetime.now(timezone.utc))
    print(json.dumps({
        "buyer_economic_gap_observation": economics,
        "schema_version": "empire.buyer_scout_resilient_recovery.v1",
        "state": "COMPLETED",
        "research_cooldown_skipped_domain_count": len(recent),
        "existing_relationship_domains_excluded": len(already_engaged),
        "mode": "OBSERVE",
        "public_search_engine_calls": 0,
        "reviewed_seed_count": len(seeds),
        "domain_count": out["domain_count"],
        "candidate_count": out["candidate_count"],
        "first_party_probes_attempted": out["probed_domain_count"],
        "canonical_empiredb_writes": False,
        "outbound_sent": False,
        "buyer_activation_authorized": False,
        "execution_authority": "none",
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
