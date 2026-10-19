#!/usr/bin/env python3
"""One-time, bounded Scout → Buyer Network private review handoff.

No canonical buyer insertion, outbound, payments, migration or timer changes.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from empire_os.acquisition_candidate_quality import quality_review, QualityHold
from empire_os.acquisition_network_handoff import build_network_admission_review, HandoffHold
class EvidenceHeld(ValueError):
    pass

SOURCES = {
    "scout": "runtime/buyer_acquisition/scout_latest.json",
    "registry": "runtime/buyer_network_intelligence/commercial_relationship_registry_latest.json",
    "network": "runtime/buyer_network_intelligence/candidate_queue_latest.json",
    "qualification": "runtime/buyer_network_intelligence/founder_qualification_actions_latest.json",
}
MAX_SIZE = {
    "scout": 5_000_000, "registry": 1_000_000,
    "network": 2_000_000, "qualification": 1_000_000,
}

def get(root: Path, key: str):
    path = root / SOURCES[key]
    if (path.is_symlink() or not path.is_file()
        or not 100 <= path.stat().st_size <= MAX_SIZE[key]
        or (key in ("registry", "qualification")
            and bool(path.stat().st_mode & 0o077))):
        raise EvidenceHeld("scoped_source_unavailable_" + key)
    raw = path.read_bytes()
    doc = json.loads(raw.decode("utf-8"))
    if not isinstance(doc, dict):
        raise EvidenceHeld("scoped_source_invalid_" + key)
    return doc, sha256(raw).hexdigest()

SCHEMA = "empire.scout_network_private_review_handoff.v1"
DEST = "runtime/buyer_network_intelligence/scout_network_review_handoff_latest_20261019.json"
KEYS = ("scout", "registry", "network", "qualification")

def _load(root):
    documents = {}
    hashes = {}
    for key in KEYS:
        doc, digest = get(root, key)
        documents[key] = doc
        hashes[key] = digest
    return documents, hashes

def _unchanged(root, hashes):
    for key, digest in hashes.items():
        path = root / SOURCES[key]
        if path.is_symlink() or not path.is_file() or sha256(path.read_bytes()).hexdigest() != digest:
            raise EvidenceHeld("source_moved_during_admission_review_" + key)

def make_review(root, *, now):
    data, original = _load(root)
    registry=data["registry"]
    if (registry.get("mode") != "OBSERVE" or
        registry.get("outbound_sent") is not False or
        not isinstance(registry.get("social_intent_review"), dict)):
        raise EvidenceHeld("review_registry_untrusted")
    research=registry["social_intent_review"].get("company_identity_research")
    if not isinstance(research,dict):
        raise EvidenceHeld("review_company_research_missing")
    q=quality_review(data["scout"], research, now=now)
    review=build_network_admission_review(data["scout"], q, data["network"], data["qualification"], now=now)
    _unchanged(root,original)
    if (review["admission_executed"] is not False or review["outbound_sent"] is not False
        or review["database_writes"] is not False or review["candidate_task_count"] > 100
        or len(review["items"]) != review["candidate_task_count"]):
        raise HandoffHold("unsafe_handoff_review_result")
    return {
        "schema_version": SCHEMA, "mode": "PRIVATE_REVIEW_ONLY",
        "generated_at": now.astimezone(timezone.utc).isoformat(),
        "source_scopes": {
            "scout_snapshot": SOURCES["scout"],
            "buyer_network_discovery_snapshot": SOURCES["network"],
            "founder_qualification_snapshot": SOURCES["qualification"],
            "social_identity_research_snapshot": SOURCES["registry"],
        },
        "source_sha256": original,
        "source_cohort_counts": {
            "scout":review["scout_discovery_denominator"],
            "network":review["buyer_network_discovery_denominator"],
            "founder_qualification":review["founder_qualification_denominator"],
            "exact_scout_network_matches":review["exact_domain_scout_to_network_matches"],
            "exact_scout_founder_matches":review["exact_domain_scout_to_founder_matches"],
        },
        "review_tasks":review["items"],
        "review_task_count":review["candidate_task_count"],
        "review_held_count":review["source_held_count"],
        "unlinked_research_count":review["unlinked_research_count"],
        "approved_buyer_admissions":0,
        "crm_contacts_created":0,
        "due_diligence_verifications_issued":0,
        "outbound_sent":False,
        "db_writes":False,
        "execution_authority":"NONE",
    }, original

def persist(root, data, hashes):
    target = root / DEST
    parent=target.parent
    if target.is_symlink() or (target.exists() and (not target.is_file() or target.stat().st_mode & 0o077)):
        raise EvidenceHeld("private_handoff_destination_untrusted")
    if not parent.is_dir():
        raise EvidenceHeld("buyer_network_runtime_directory_missing")
    _unchanged(root, hashes)
    fd, name = None, None
    try:
        with NamedTemporaryFile("w",prefix=".scout_network_review_",
                                suffix=".tmp",dir=parent,encoding="utf-8",delete=False) as out:
            name=out.name
            os.chmod(name,0o600)
            json.dump(data,out,sort_keys=True,separators=(",",":"))
            out.write("\n")
            out.flush()
            os.fsync(out.fileno())
        _unchanged(root, hashes)
        os.replace(name,target)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)
    return target

def main():
    parser=argparse.ArgumentParser()
    flags=parser.add_mutually_exclusive_group(required=True)
    flags.add_argument("--read-only",action="store_true")
    flags.add_argument("--record-private-review",action="store_true")
    parser.add_argument("--repo-root",default="/srv/empire_os")
    args=parser.parse_args()
    try:
        root=Path(args.repo_root)
        data,hashes=make_review(root,now=datetime.now(timezone.utc))
        if args.record_private_review:
            os.umask(0o077)
            path=persist(root,data,hashes)
            print(json.dumps({"status":"PRIVATE_SCOUT_NETWORK_REVIEW_RECORDED",
                             "review_tasks":data["review_task_count"],
                             "held_sources":data["review_held_count"],
                             "approved_buyer_admissions":0,
                             "outbound_sent":False,"db_writes":False}))
        else:
            print(json.dumps(data,indent=2,sort_keys=True))
        return 0
    except (EvidenceHeld,QualityHold,HandoffHold,ValueError,UnicodeError,OSError,KeyError,TypeError):
        print(json.dumps({"status":"HOLD_SCOUT_NETWORK_SOURCE_INTEGRITY",
                          "outbound_sent":False,"db_writes":False}))
        return 3

if __name__=="__main__":
    raise SystemExit(main())
