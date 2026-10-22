"""One-shot Jev pre-offer evidence receipt; no contacts or production writes."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

from empire_os.jev_preoffer_evidence_review import review_preoffer

ROOT = Path("/srv/empire_os")
COUNTERPARTY = Path("docs/commercial/JEV_B2B_SUPPLIER_REQUESTS_COUNTERPARTY_READINESS_20261022.json")
ORIGINAL = Path("docs/commercial/JEV_EXTERNAL_PUBLIC_B2B_NEED_CANDIDATES_20261022.json")
SUPPLY = ROOT / "runtime/lead_supply/private_leadgen/research_queue_latest.json"
OUTPUT = Path("docs/commercial/JEV_PUBLIC_TWO_CASE_PREOFFER_REVIEW_20261022.json")


def _read(path: Path, max_bytes: int) -> dict:
    if (path.is_symlink() or not path.is_file()
        or not 0 < path.stat().st_size <= max_bytes):
        raise ValueError("bounded original source unavailable")
    obj = json.loads(path.read_text(encoding="utf8"))
    if not isinstance(obj, dict):
        raise ValueError("expected original evidence summary")
    return obj


def review_live() -> dict:
    repo = Path(__file__).resolve().parents[1]
    case = _read(repo / COUNTERPARTY, 100000)
    original = repo / ORIGINAL
    if case.get("original_public_manual_source_sha256") != sha256(original.read_bytes()).hexdigest():
        raise ValueError("manual source evidence fingerprint drift")
    supply = _read(SUPPLY, 150000)
    review = review_preoffer(case, supply, as_of=datetime.now(timezone.utc))
    review["counterparty_receipt_sha256"] = sha256((repo / COUNTERPARTY).read_bytes()).hexdigest()
    review["original_public_source_fingerprint_verified"] = True
    review["lead_supply_snapshot_observed_at"] = supply.get("generated_at")
    review["recipient_records_opened"] = 0
    return review


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--read-only", required=True, action="store_true")
    parser.parse_args()
    dest = Path(__file__).resolve().parents[1] / OUTPUT
    if dest.exists() or dest.is_symlink() or not dest.parent.is_dir():
        raise ValueError("read-only review receipt already exists")
    review = review_live()
    with dest.open("x", encoding="utf8") as out:
        json.dump(review, out, sort_keys=True, indent=2)
        out.write("\n")
    print(json.dumps({
        "status":review["status"],
        "source_state":review["lead_supply_status"],
        "selected":review["lead_supply_counts"]["selected"],
        "ready":review["lead_supply_counts"]["sellable"],
        "offer_ready":review["commercial_offers_ready"],
        "outbound":review["messages_sent"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
