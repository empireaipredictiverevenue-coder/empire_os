"""Read-only preflight for original genuine CRM founder tenant; prints NO IDs, emails or secrets."""
from __future__ import annotations
import json
import subprocess

SQL = """
BEGIN TRANSACTION READ ONLY;
SET LOCAL statement_timeout='3000ms';
SELECT
 (SELECT COUNT(DISTINCT tenant_id) FROM public.empire_crm_tenant_memberships
  WHERE role='owner' AND status='active' AND revoked_at IS NULL
    AND verified_at<=CURRENT_TIMESTAMP
    AND (valid_until IS NULL OR valid_until>CURRENT_TIMESTAMP)
    AND length(btrim(evidence_ref))>0) AS active_owner_tenant_count,
 (SELECT COUNT(*) FROM public.empire_crm_tenant_memberships AS m
  JOIN public.empire_crm_login_credentials AS c
   ON c.subject=m.subject AND c.invitation_tenant_id=m.tenant_id
  WHERE m.role='owner' AND m.status='active' AND m.revoked_at IS NULL
    AND m.verified_at<=CURRENT_TIMESTAMP
    AND (m.valid_until IS NULL OR m.valid_until>CURRENT_TIMESTAMP)
    AND length(btrim(m.evidence_ref))>0
    AND c.status='active' AND c.password_change_required=false
    AND c.invitation_redeemed_at IS NOT NULL
    AND c.verified_at<=CURRENT_TIMESTAMP
    AND length(btrim(c.evidence_ref))>0) AS authenticated_owner_member_matches,
 (SELECT COUNT(DISTINCT m.tenant_id) FROM public.empire_crm_tenant_memberships AS m
  JOIN public.empire_crm_login_credentials AS c
   ON c.subject=m.subject AND c.invitation_tenant_id=m.tenant_id
  WHERE m.role='owner' AND m.status='active' AND m.revoked_at IS NULL
    AND m.verified_at<=CURRENT_TIMESTAMP
    AND (m.valid_until IS NULL OR m.valid_until>CURRENT_TIMESTAMP)
    AND length(btrim(m.evidence_ref))>0
    AND c.status='active' AND c.password_change_required=false
    AND c.invitation_redeemed_at IS NOT NULL
    AND c.verified_at<=CURRENT_TIMESTAMP
    AND length(btrim(c.evidence_ref))>0) AS credentialed_owner_tenant_count;
COMMIT;
"""
cmd=["sudo","-n","runuser","-u","postgres","--","psql",
     "-XAt","-w","-v","ON_ERROR_STOP=1","-d","empiredb","-c",SQL]
r=subprocess.run(cmd,capture_output=True,text=True,timeout=12)
if r.returncode:
    print(json.dumps({"status":"CANONICAL_CRM_OWNER_PROOF_UNAVAILABLE","database_changes":False}))
else:
    rows=[v for v in r.stdout.splitlines() if "|" in v]
    if len(rows)!=1:
        raise RuntimeError("ambiguous_owner_count")
    counts=[int(x) for x in rows[0].split("|")]
    if len(counts)!=3:
        raise RuntimeError("owner_count_schema_drift")
    print(json.dumps({
        "status":"READ_ONLY_CRM_OWNER_PREFLIGHT",
        "active_owner_tenant_count":counts[0],
        "active_credentialed_owner_memberships":counts[1],
        "active_credentialed_owner_tenant_count":counts[2],
        "single_genuine_active_founder_tenant_verified":counts==[1,1,1],
        "tenant_id_exposed":False,
        "database_changes":False,
    },sort_keys=True))
