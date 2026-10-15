"""Founder-operated one-hit aggregate of canonical EmpireDB sales acquisitions.

Explicitly privileged, local, READ ONLY transaction. Prints counts only:
never prospect IDs, emails, domains, contact data, tenant ID, credentials,
SQL driver diagnostics or source evidence bodies. It does NOT bind tenants.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from uuid import UUID

from scripts.repair_crm_login_passfile_lookup import TENANT

SCHEMA = "empire.founder.canonical_sales_source_aggregate.v1"

# No DML or bypassing tenant access in product code. An explicitly authorised
# local operator uses postgres to diagnose if/where founder visibility is absent.
SQL = r"""
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL statement_timeout = '10000ms';
SET LOCAL lock_timeout = '2000ms';
WITH sales AS MATERIALIZED (
    SELECT a.prospect_id, a.source, a.evidence
    FROM public.prospect_acquisitions a
    WHERE a.source IN (
        'first_party_commercial_sales_enquiry',
        'self_serve_predictive_revenue'
    )
), mapped AS (
    SELECT s.source, s.prospect_id,
           s.evidence->>'source' = s.source AS source_matches,
           s.evidence->>'buyer_stated' = 'true' AS buyer_stated,
           -- Both first-party commercial and Predictive Revenue routes
           -- require explicit response consent. A legacy ELSE TRUE treated
           -- predictive source rows as consented even if proof was absent.
           (
             s.evidence #>> '{contact_consent_evidence,kind}'
                = 'buyer_initiated_specific_response_consent'
             AND s.evidence #>> '{contact_consent_evidence,consent_to_contact}'
                = 'true'
             AND s.evidence #>> '{contact_consent_evidence,newsletter_or_ongoing_marketing_consent}'
                = 'false'
             AND s.evidence #>> '{contact_consent_evidence,source_url}'
                = CASE
                    WHEN s.source = 'first_party_commercial_sales_enquiry'
                      THEN 'https://empire-ai.co.uk/commercial'
                    ELSE 'https://empire-ai.co.uk/predictive-revenue'
                  END
           ) AS consent_evidence,
           EXISTS (
               SELECT 1 FROM public.prospect_entity_links link
               WHERE link.prospect_id=s.prospect_id
                 AND link.active IS TRUE
                 AND link.evidence <> '{}'::jsonb
           ) AS has_evidenced_entity_link,
           (
               SELECT count(*)
               FROM public.prospect_entity_links link
               JOIN public.tenant_business_entity_bindings binding
                 ON binding.entity_id=link.entity_id
               WHERE link.prospect_id=s.prospect_id
                 AND link.active IS TRUE
                 AND link.evidence IS NOT NULL
                 AND link.evidence <> '{}'::jsonb
                 AND binding.tenant_id=:'founder_tenant'::uuid
                 AND binding.active IS TRUE
                 AND binding.binding_kind IN ('owned','managed','customer','prospect')
                 AND binding.evidence_ref IS NOT NULL
                 AND length(btrim(binding.evidence_ref))>0
                 AND binding.valid_from <= CURRENT_TIMESTAMP
                 AND (binding.valid_until IS NULL OR binding.valid_until > CURRENT_TIMESTAMP)
           ) AS founder_binding_matches
    FROM sales s
)
SELECT jsonb_build_object(
  'commercial_acquisition_rows', count(*) FILTER
    (WHERE source='first_party_commercial_sales_enquiry'),
  'predictive_acquisition_rows', count(*) FILTER
    (WHERE source='self_serve_predictive_revenue'),
  'sales_acquisition_rows', count(*),
  'distinct_sales_prospects', count(DISTINCT prospect_id),
  'source_evidence_consistent_rows', count(*) FILTER
    (WHERE source_matches AND buyer_stated AND consent_evidence),
  'entity_unlinked_acquisition_rows', count(*) FILTER
    (WHERE NOT has_evidenced_entity_link),
  'founder_binding_exact_one_rows', count(*) FILTER
    (WHERE founder_binding_matches=1),
  'founder_binding_missing_or_ambiguous_rows', count(*) FILTER
    (WHERE founder_binding_matches<>1)
)::text
FROM mapped;
ROLLBACK;
"""

COUNT_KEYS = (
    "commercial_acquisition_rows", "predictive_acquisition_rows",
    "sales_acquisition_rows", "distinct_sales_prospects",
    "source_evidence_consistent_rows", "entity_unlinked_acquisition_rows",
    "founder_binding_exact_one_rows",
    "founder_binding_missing_or_ambiguous_rows",
)


def classify(*, privileged: bool, returncode: int, stdout: str) -> dict:
    result = {
        "schema_version": SCHEMA, "mode": "OBSERVE",
        "read_only": True, "source": "CANONICAL_EMPIREDB",
        "customer_rows_disclosed": False, "contact_data_disclosed": False,
        "tenant_identifier_disclosed": False,
        "prospect_links_changed": False, "database_writes": False,
        "outbound_sent": False, "payment_action": False,
        "execution_authority": "NONE",
        "founder_crm_delivery_verified": False,
    }
    if not privileged:
        result.update(status="BLOCKED", reason_code="PRIVILEGED_LOCAL_OPERATOR_REQUIRED")
        return result
    if returncode != 0:
        result.update(status="UNVERIFIED", reason_code="CANONICAL_QUERY_FAILED")
        return result
    try:
        lines = [x.strip() for x in stdout.splitlines() if x.strip().startswith("{")]
        if len(lines) != 1:
            raise ValueError("unexpected output")
        data = json.loads(lines[0])
        if (not isinstance(data, dict) or set(data) != set(COUNT_KEYS)
                or any(type(data[k]) is not int or data[k] < 0 for k in COUNT_KEYS)
                or data["commercial_acquisition_rows"]+data["predictive_acquisition_rows"]
                     != data["sales_acquisition_rows"]
                or data["distinct_sales_prospects"] > data["sales_acquisition_rows"]
                or data["source_evidence_consistent_rows"] > data["sales_acquisition_rows"]
                or data["entity_unlinked_acquisition_rows"] > data["sales_acquisition_rows"]
                or data["founder_binding_exact_one_rows"]
                   +data["founder_binding_missing_or_ambiguous_rows"]
                   != data["sales_acquisition_rows"]):
            raise ValueError("untrusted count")
    except (ValueError, TypeError, KeyError):
        result.update(status="UNVERIFIED", reason_code="SOURCE_COUNTS_UNTRUSTED")
        return result
    result.update(data)
    result["status"] = (
        "NO_SALES_ACQUISITION_IN_CANONICAL_SOURCE"
        if data["sales_acquisition_rows"] == 0
        else "SALES_ACQUISITION_SOURCE_OBSERVED_REVIEW_REQUIRED"
    )
    # Source evidence/tenant-link COUNT is not actual founder sign-in proof.
    result["founder_crm_delivery_verified"] = False
    return result


def run(*, euid: int | None = None, command_runner=None) -> dict:
    uid = os.geteuid() if euid is None else euid
    if uid != 0:
        return classify(privileged=False, returncode=2, stdout="")
    try:
        tenant = str(UUID(TENANT))
    except (ValueError, TypeError, AttributeError):
        return classify(privileged=True, returncode=1, stdout="")
    command = [
        "/usr/sbin/runuser", "-u", "postgres", "--",
        "/usr/bin/psql", "-X", "-q", "-w", "-A", "-t",
        "-v", "ON_ERROR_STOP=1", "-v", "founder_tenant=" + tenant,
        "-h", "/var/run/postgresql", "-d", "empiredb", "-f", "-",
    ]
    runner = subprocess.run if command_runner is None else command_runner
    try:
        proc = runner(command, input=SQL, text=True, capture_output=True,
                      timeout=16, check=False, env={
                          "PATH": "/usr/bin:/bin", "LC_ALL": "C",
                          "PGCONNECT_TIMEOUT": "4",
                      })
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return classify(privileged=True, returncode=1, stdout="")
    return classify(privileged=True, returncode=proc.returncode,
                    stdout=proc.stdout)


def main() -> int:
    report=run()
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"] not in ("UNVERIFIED","BLOCKED") else 2


if __name__ == "__main__":
    raise SystemExit(main())
