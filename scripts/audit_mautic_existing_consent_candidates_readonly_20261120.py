#!/usr/bin/env python3
"""Read-only first-party marketing-consent candidate census for Mautic.

This is an eligibility *screen*, not identity proof, consent adjudication
or permission to import, contact, publish or bind any prospect.

Uses existing canonical public.prospect_acquisitions in EmpireDB; no PII,
prospect IDs, emails, source body or tenant IDs are emitted. Runs as a
privileged read-only canonical DB owner, not as any tenant application role.
"""
from __future__ import annotations

import json
import os
import subprocess

SQL = """
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL statement_timeout='7000ms';
SET LOCAL lock_timeout='1000ms';
WITH raw AS MATERIALIZED (
    SELECT source, evidence, prospect_id,
      (evidence #>> '{contact_consent_evidence,newsletter_or_ongoing_marketing_consent}') AS ongoing_marketing_claim,
      (evidence #>> '{contact_consent_evidence,kind}') AS consent_kind,
      (evidence #>> '{contact_consent_evidence,consent_to_contact}') AS response_claim
    FROM public.prospect_acquisitions
    WHERE evidence ? 'contact_consent_evidence'
)
SELECT jsonb_build_object(
    'consent_evidence_rows', count(*),
    'ongoing_marketing_claim_true_rows',
       count(*) FILTER (WHERE ongoing_marketing_claim = 'true'),
    'response_only_consent_rows',
       count(*) FILTER (WHERE consent_kind = 'buyer_initiated_specific_response_consent'
                   AND response_claim = 'true'
                   AND ongoing_marketing_claim = 'false'),
    'ongoing_marketing_claim_rows_with_prospect_id',
       count(*) FILTER (WHERE ongoing_marketing_claim = 'true' AND prospect_id IS NOT NULL),
    'first_party_commercial_marketing_claim_true',
       count(*) FILTER (WHERE source = 'first_party_commercial_sales_enquiry'
                   AND ongoing_marketing_claim = 'true')
)::text FROM raw;
ROLLBACK;
"""

def classify(result: subprocess.CompletedProcess[str] | None) -> dict[str, object]:
    held = {
        "schema_version": "empire.mautic.existing_consent_candidates_readonly.v1",
        "status": "CANONICAL_SOURCE_NOT_READABLE_HOLD",
        "read_only": True,
        "no_customer_identifiers_disclosed": True,
        "mautic_contacts_created": False,
        "source_mapping_authorized": False,
        "outbound_authorized": False,
        "marketing_consent_verified": False,
    }
    if result is None or result.returncode != 0 or len(result.stdout) > 4000:
        return held
    try:
        rows = [v.strip() for v in result.stdout.splitlines() if v.strip().startswith("{")]
        if len(rows) != 1:
            return held
        record = json.loads(rows[0])
        required = {
            'consent_evidence_rows', 'ongoing_marketing_claim_true_rows',
            'response_only_consent_rows',
            'ongoing_marketing_claim_rows_with_prospect_id',
            'first_party_commercial_marketing_claim_true',
        }
        if set(record) != required or any(
            type(v) is not int or not 0 <= v <= 10_000_000 for v in record.values()
        ):
            return held
        if any(v > record['consent_evidence_rows'] for v in record.values()):
            return held
    except (TypeError, ValueError, json.JSONDecodeError):
        return held
    return {
        **held,
        'status': 'CENSUS_COMPLETE_CLAIMS_ONLY_NOT_CONTACT_AUTHORITY',
        'counts': record,
    }


def run() -> dict[str, object]:
    if os.geteuid() != 0:
        return classify(None)
    try:
        proc = subprocess.run(
            ["/usr/sbin/runuser", "-u", "postgres", "--",
             "/usr/bin/psql", "-X", "-q", "-w", "-A", "-t",
             "-v", "ON_ERROR_STOP=1",
             "-h", "/var/run/postgresql", "-d", "empiredb", "-f", "-"],
            input=SQL, text=True, capture_output=True, timeout=12,
            env={"PATH": "/usr/bin:/bin", "LC_ALL": "C", "PGCONNECT_TIMEOUT": "4"},
            check=False,
        )
        return classify(proc)
    except (OSError, subprocess.TimeoutExpired):
        return classify(None)

if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True))
