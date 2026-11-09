"""One-off owner review: pin an independently fetched public-register observation.

Modifies only the *existing* review packet inside this git worktree, and ONLY
on an exact preimage. Reuses original V4.11 research-only / HELD admission;
does not create a provider adapter, tenant binding, API, service or grant.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "docs/PREDICTIVE_CLOUD_FIRST_PARTY_RESEARCH_COHORT_20261108.json"
PREIMAGE_SHA = "eb1de47764a6100b82dc36ba6246e445f777a594bbd6d31a8d0bc19037dee657"
UK_URL = "https://find-and-update.company-information.service.gov.uk/company/02745893"
POLICY_URL = ("https://www.gov.uk/government/publications/"
              "companies-house-accreditation-to-information-fair-traders-scheme/"
              "public-task-copyright-and-crown-copyright")
DATASET_URL = "https://data.texas.gov/dataset/TDLR-All-Licenses/7358-krk7"

OFFICIAL_FIELDS = {
    "company_number": "02745893",
    "company_name": "ICH SERVICES LTD",
    "company_status": "Active",
    "incorporation_date": "1992-09-09",
    "registered_address": "Union Bridge Works, Roker Lane, Pudsey, LS28 9LE",
    "sic_codes": ["43210", "43220", "81100"],
}

class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
    def handle_data(self, value):
        self.parts.append(value)


def company_page_facts(page: bytes) -> None:
    parser = VisibleText()
    parser.feed(page.decode("utf-8"))
    text = " ".join(" ".join(parser.parts).split()).casefold()
    tokens = (
        "ich services ltd", "02745893", "union bridge works",
        "roker lane", "company status active",
        "9 september 1992", "43210", "43220", "81100"
    )
    if any(token not in text for token in tokens):
        raise ValueError("official_company_page_fact_not_observed")


def run(*, apply_existing_packet: bool) -> dict:
    if PACKET.is_symlink() or not PACKET.is_file():
        raise ValueError("original_evidence_packet_missing_or_symlink")
    info = PACKET.stat()
    if (info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o644
            or info.st_size > 100000):
        raise ValueError("original_evidence_packet_ownership_or_size_changed")
    raw = PACKET.read_bytes()
    if sha256(raw).hexdigest() != PREIMAGE_SHA:
        raise ValueError("original_evidence_packet_preimage_changed")
    original = json.loads(raw)
    if (original.get("schema_version") !=
            "empire.predictive_cloud.first_party_research_cohort.v1"
            or original.get("mode") != "RESEARCH_ONLY"
            or original.get("execution_authority") != "none"
            or len(original.get("records", [])) != 4):
        raise ValueError("source_review_contract_drift")
    uk = [r for r in original["records"]
          if r.get("domain") == "ich-services.co.uk"
          and r.get("research_policy") == "PASS_RESEARCH_ONLY"
          and r.get("customer_delivery_authorized") is False]
    if len(uk) != 1 or "official_uk_source_observation" in uk[0]:
        raise ValueError("exact_original_uk_candidate_missing_or_modified")

    result = subprocess.run(
        ["curl", "-fsSL", "--max-time", "15", "--compressed", UK_URL],
        capture_output=True, timeout=20, check=False,
    )
    if result.returncode or not 10000 <= len(result.stdout) <= 250000:
        raise ValueError("independent_official_source_unavailable")
    company_page_facts(result.stdout)

    evidence_sha = sha256(json.dumps(
        OFFICIAL_FIELDS, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")).hexdigest()
    observation = {
        "schema_version": "empire.predictive_cloud.official_source_research.v1",
        "source_kind": "independent_uk_public_company_register",
        "source_url": UK_URL,
        "official_response_sha256": sha256(result.stdout).hexdigest(),
        "official_response_bytes": len(result.stdout),
        "source_observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_evidence_digest": evidence_sha,
        "public_register_fields": OFFICIAL_FIELDS,
        "permitted_purpose_candidate": "PRIVATE_PREDICTIVE_RESEARCH_ONLY",
        "source_reuse_policy_url": POLICY_URL,
        "public_register_reuse_policy": "REUSE_PERMITTED_SUBJECT_TO_APPLICABLE_LAW",
        "personal_data_in_this_observation": False,
        "source_rights_document_has_been_owner_attested": False,
        "original_signed_crm_tenant_bound": False,
        "restricted_empiredb_rights_reader_verified": False,
        "production_source_admitted": False,
        "redis_publish_authorized": False,
        "customer_forecast_verified": False,
        "customer_delivery_authorized": False,
        "paid_provider_call": False,
        "execution_authority": "none",
    }
    if not apply_existing_packet:
        return {"preflight": "PASS", "changes": False, "source_response_sha256":
                observation["official_response_sha256"],
                "source_evidence_digest": evidence_sha,
                "production_source_admitted": False}

    uk[0]["official_uk_source_observation"] = observation
    for item in original["source_rights"]:
        if item.get("source") == "Companies House UK public register":
            item["public_register_reuse_policy_verified_against_gov_uk"] = True
            item["exact_product_customer_publication_approved"] = False
        if item.get("source") == "Texas TDLR open-data licence register":
            item["dataset_license_listing"] = "unspecified"
            item["source_license_for_external_resale_verified"] = False
            item["source_license_listing_url"] = DATASET_URL
    if not any(x.get("source") == "Texas TDLR open-data licence register"
               for x in original["source_rights"]):
        original["source_rights"].append({
            "source": "Texas TDLR open-data licence register",
            "portal_url": DATASET_URL,
            "dataset_last_updated": "2026-09-19",
            "dataset_license_listing": "unspecified",
            "source_license_for_external_resale_verified": False,
            "public_readable": True,
            "customer_delivery_authorized_by_this_review": False,
        })
    original["provenance_controls"]["independent_uk_public_register_response_sha256_captured"] = True
    original["provenance_controls"]["source_admitted_into_predictive_cloud"] = False
    original["provenance_controls"]["paid_provider_calls"] = False

    destination = PACKET.parent
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=destination,
        prefix=".official-source-review-", delete=False
    ) as f:
        tmp = Path(f.name)
        try:
            os.fchmod(f.fileno(), 0o644)
            json.dump(original, f, ensure_ascii=False, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise
    try:
        if sha256(PACKET.read_bytes()).hexdigest() != PREIMAGE_SHA:
            raise ValueError("source_packet_changed_during_review")
        os.replace(tmp, PACKET)
    finally:
        tmp.unlink(missing_ok=True)
    return {"preflight": "PASS", "changed_review_packet_only": True,
            "source_evidence_digest": evidence_sha,
            "original_crm_tenant_bound": False, "production_source_admitted": False,
            "paid_provider_calls": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--preflight-read-only", action="store_true")
    group.add_argument("--apply-review-packet-only", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(apply_existing_packet=args.apply_review_packet_only),
                     sort_keys=True))
