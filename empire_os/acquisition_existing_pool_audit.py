"""Read-only, provenance-preserving audit of the existing YC pool and GTM radar.

Sources are the prior agent's committed YC CSV and the current owner-generated
GTM/radar snapshots. Directory profiles and Jev/market inferences are research
evidence, not verified buyers, contact permissions, or model-training truth.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta, timezone
import csv
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
import subprocess
from urllib.parse import urlparse

from empire_os.acquisition_search_jev_bridge import summarize_search_jev_acquisition
from empire_os.acquisition_segment_learning import segment_pool

YC_COMMIT = "32dcfa38e"
YC_PATH = "research_reviews/data/YC_US_UK_500_SEGMENTED_20261022.csv"
REQUIRED_COLUMNS = {
    "company", "yc_profile", "region", "research_segment", "verification_status",
    "buyer_intent", "approval_state", "next_evidence", "sector"
}
MAX_POOL = 1000
MAX_AGE = timedelta(hours=24)


def load_committed_yc_pool(repo: Path, *, commit: str = YC_COMMIT) -> tuple[list[dict[str, str]], str]:
    """Read the original committed data without checkout or repository mutation."""
    if not commit.isalnum() or len(commit) > 40:
        raise ValueError("invalid immutable commit identifier")
    result = subprocess.run(
        ["git", "-C", str(repo), "show", f"{commit}:{YC_PATH}"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=10,
    )
    if result.returncode or not result.stdout or len(result.stdout) > 2_000_000:
        raise ValueError("committed YC pool unavailable or outside size limit")
    raw = result.stdout.decode("utf-8-sig")
    reader = csv.DictReader(StringIO(raw))
    if not reader.fieldnames or not REQUIRED_COLUMNS <= set(reader.fieldnames):
        raise ValueError("YC dataset lacks required evidence columns")
    rows = list(reader)
    if not rows or len(rows) > MAX_POOL:
        raise ValueError("YC pool outside bounded size")
    seen = set()
    for row in rows:
        url = row.get("yc_profile") or ""
        parsed = urlparse(url)
        if (parsed.scheme != "https" or parsed.hostname not in
                ("www.ycombinator.com", "ycombinator.com")
                or not parsed.path.startswith("/companies/") or url in seen):
            raise ValueError("invalid or duplicate YC identity source")
        seen.add(url)
    return rows, sha256(result.stdout).hexdigest()


def _fresh(payload: Mapping, now: datetime) -> bool:
    try:
        stamped = datetime.fromisoformat(str(payload["generated_at"]).replace("Z", "+00:00"))
        age = now.astimezone(timezone.utc) - stamped.astimezone(timezone.utc)
        return -timedelta(minutes=5) <= age <= MAX_AGE
    except (ValueError, TypeError, KeyError):
        return False


def audit_existing_acquisition_sources(
    *, yc_rows: Sequence[Mapping[str, str]], yc_sha256: str,
    gtm: Mapping, radar: Mapping, now: datetime,
) -> dict:
    if now.tzinfo is None or not isinstance(gtm, Mapping) or not isinstance(radar, Mapping):
        raise ValueError("timestamped existing owner snapshots required")
    if (gtm.get("schema_version") != "empire.gtm.integration_observer.v1"
        or radar.get("schema_version") != "empire.predictive_cloud.opportunity_radar.v1"
        or gtm.get("radar_evidence_current") is not True
        or gtm.get("execution_authority") != "none"
        or radar.get("execution_authority") != "none"
        or radar.get("mode") != "OBSERVE"
        or not _fresh(gtm, now) or not _fresh(radar, now)):
        raise ValueError("fresh read-only GTM and radar evidence required")
    if not isinstance(yc_rows, (tuple, list)) or not 1 <= len(yc_rows) <= MAX_POOL:
        raise ValueError("bounded source pool required")
    if not isinstance(yc_sha256, str) or len(yc_sha256) != 64:
        raise ValueError("source digest required")

    # Explicit first-pass: directory records cannot become buyer-qualified via
    # hiring flags, category matches, arbitrary scores, or inferred pain alone.
    identities = set()
    research_records = []
    regions = Counter()
    blockers = Counter()
    research_queue = []
    for row in yc_rows:
        if not isinstance(row, Mapping):
            raise ValueError("YC record mapping required")
        url = row.get("yc_profile")
        if not isinstance(url, str) or url in identities or not url:
            raise ValueError("duplicate or missing YC profile")
        identities.add(url)
        if (row.get("verification_status") != "public_directory_only"
            or row.get("buyer_intent") != "UNVERIFIED"
            or row.get("approval_state") != "RESEARCH_ONLY"):
            raise ValueError("unexpected YC evidence status; require new owner validation")
        region = row.get("region") or "unknown"
        regions[region] += 1
        segment = row.get("research_segment") or "unclassified"
        blockers["company_identity_independent_verification"] += 1
        blockers["dated_buyer_need_and_offer_fit"] += 1
        blockers["suppression_and_contact_permission"] += 1
        # Priority is an internal research ordering, not buyer intent.
        try:
            priority = int(row.get("research_priority_score") or 0)
        except (ValueError, TypeError):
            priority = 0
        if not 0 <= priority <= 100:
            priority = 0
        research_queue.append({
            "prospect_ref": sha256(url.encode()).hexdigest()[:24],
            "company": str(row.get("company") or "")[:120],
            "niche": str(segment)[:80],
            "product_code": "unclassified",
            "priority_for_research_only": priority,
            "source_url": url,
            "evidence_to_verify": str(row.get("next_evidence") or
                                      "Verify dated company-specific commercial need")[:220],
            "contact_authorized": False,
            "status": "RESEARCH_ONLY",
        })
        research_records.append({
            "prospect_ref": sha256(url.encode()).hexdigest()[:24],
            "niche": str(segment)[:80],
            "product_code": "unclassified",
            # The canonical pool assessor has no verified company / trigger /
            # product / offer authority from this directory.
            "company_identity_verified": False,
            "dated_commercial_trigger_verified": False,
            "product_fit_verified": False,
        })
    segmented = segment_pool(lane="vc_portfolio", records=research_records)
    gtm_review = summarize_search_jev_acquisition(gtm)
    candidates = radar.get("candidates")
    if not isinstance(candidates, list) or len(candidates) > 100:
        raise ValueError("bounded canonical radar candidates required")
    radar_by_key = {c.get("opportunity_key"): c for c in candidates if isinstance(c, Mapping)}
    market = Counter()
    products = Counter()
    verified_handoff_matches = 0
    for h in gtm.get("handoffs", []):
        c = radar_by_key.get(h.get("opportunity_key"))
        if not isinstance(c, Mapping) or c.get("source") != h.get("source"):
            continue
        if (h.get("product_key") or None) != (c.get("offer_key") or None):
            continue
        # Even a match is a research signal, never a confirmed buyer.
        if c.get("commercial_demand_observed") is True or c.get("buyer_intent_inferred") is True:
            continue
        verified_handoff_matches += 1
        niche = c.get("niche")
        market[niche if isinstance(niche, str) and niche else "unclassified"] += 1
        product = c.get("offer_key")
        products[product if isinstance(product, str) and product else "unclassified"] += 1

    return {
        "schema_version": "empire.acquisition_existing_pool_audit.v1",
        "mode": "OBSERVE",
        "yc_source_commit": YC_COMMIT,
        "yc_source_sha256": yc_sha256,
        "yc_directory_records": len(yc_rows),
        "yc_regions": dict(sorted(regions.items())),
        "yc_segments": segmented["segments"],
        "next_research_batch": sorted(research_queue, key=lambda r: (
            -r["priority_for_research_only"], r["company"].casefold()))[:20],
        "yc_qualified_for_review": segmented["segments"] and sum(
            s["qualified_for_review"] for s in segmented["segments"]) or 0,
        "yc_contact_review_ready": 0,
        "yc_evidence_gaps": dict(blockers),
        "gtm_research_handoffs": gtm_review["research_handoff_count"],
        "gtm_radar_correlated_handoffs": verified_handoff_matches,
        "gtm_niche_counts": dict(sorted(market.items())),
        "gtm_product_counts": dict(sorted(products.items())),
        "status": "RESEARCH_EVIDENCE_ONLY",
        "buyer_identity_verified": False,
        "qualified_buyers_claimed": 0,
        "canonical_empiredb_connected": False,
        "crm_writes": False,
        "outbound_authorized": False,
        "model_training_authorized": False,
        "verified_revenue": None,
    }


def read_only_current_snapshot(repo: Path, *, now: datetime | None = None) -> dict:
    rows, digest = load_committed_yc_pool(repo)
    gtm = json.loads((repo / "runtime/gtm_pipeline/integration_observer_latest.json").read_text())
    radar = json.loads((repo / "runtime/opportunity_radar/latest.json").read_text())
    return audit_existing_acquisition_sources(
        yc_rows=rows, yc_sha256=digest, gtm=gtm, radar=radar,
        now=now or datetime.now(timezone.utc),
    )


if __name__ == "__main__":
    print(json.dumps(read_only_current_snapshot(Path(__file__).resolve().parent.parent), indent=2))
