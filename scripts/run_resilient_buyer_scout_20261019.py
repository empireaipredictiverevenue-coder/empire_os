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
from empire_os.leadgen_contact_history_bridge import DOMAIN, TECHNICAL_HOSTS

DEFAULT_ROOT = Path("/srv/empire_os")
SOURCE = "runtime/buyer_network_intelligence/founder_qualification_actions_latest.json"


def reviewed_seed_records(snapshot: dict, *, limit: int = 8,
                          rotation: int = 0) -> list[dict]:
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
                or domain.endswith(TECHNICAL_HOSTS) or domain in domains):
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
    slot = int(datetime.now(timezone.utc).timestamp() // 1800)
    seeds = reviewed_seed_records(data, limit=args.max_seeds, rotation=slot)
    if not seeds:
        raise SystemExit("no_reviewed_b2b_seeds")
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
    print(json.dumps({
        "schema_version": "empire.buyer_scout_resilient_recovery.v1",
        "state": "COMPLETED",
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
