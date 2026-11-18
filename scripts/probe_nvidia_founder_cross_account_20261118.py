"""Read-only account-link evidence before any founder-approved NVIDIA grant.

Confirms original NVIDIA OAuth userinfo is verified and compares only within
the trusted host against the original CRM founder invitation. Returns and
stores booleans only: no login emails, subjects, bearer tokens or invitations
are disclosed. A mismatch or unredeemed CRM invitation cannot silently
authorize linking distinct accounts.
"""
from __future__ import annotations
import json,os
from pathlib import Path
import httpx

from scripts.verify_nvidia_viewer_real_mcp_tools_20261117 import load_existing_grant

OUT=Path("/srv/empire_os/runtime/nvidia_ontology_eval/nvidia_founder_cross_account_preflight_20261118.json")
CRM=Path("/var/lib/empire-crm-first-party/founder_invitation/pending_invitation.json")
URL="http://localhost:33000/api/auth/oauth2/userinfo"

def main():
    if OUT.exists():raise RuntimeError("immutable account-link preflight exists")
    if CRM.is_symlink() or not CRM.is_file() or CRM.stat().st_mode&0o077:
        raise RuntimeError("original private founder CRM evidence unavailable")
    original=json.loads(CRM.read_text())
    with httpx.Client(timeout=12,trust_env=False,follow_redirects=False) as c:
        response=c.get(URL,headers={"Authorization":"Bearer "+load_existing_grant()})
    if response.status_code!=200:
        raise RuntimeError("original Viewer OAuth userinfo authentication failed")
    info=response.json()
    if not isinstance(info,dict):
        raise RuntimeError("NVIDIA userinfo malformed")
    email_present=isinstance(info.get("email"),str) and bool(info["email"])
    verified=info.get("email_verified") is True
    subject_present=isinstance(info.get("sub"),str) and bool(info["sub"])
    matches=email_present and info["email"].casefold()==str(original.get("login_email") or "").casefold()
    crm_pending=original.get("status")=="PENDING_NOT_SENT"
    report={
        "status":"NVIDIA_VIEWER_VERIFIED_FOUNDER_CROSS_ACCOUNT_APPROVAL_REQUIRED",
        "nvidia_userinfo_http":response.status_code,
        "nvidia_verifiable_subject_present":bool(subject_present),
        "nvidia_verified_email":bool(verified),
        "nvidia_email_matches_original_crm_founder_invitation":bool(matches),
        "original_crm_invitation_pending_not_sent":crm_pending,
        "nvidia_to_empire_subject_link_signed":False,
        "customer_tenant_access_granted":False,
        "silent_link_by_email_permitted":False,
        "independent_founder_account_link_approval_required":True,
        "no_private_identity_or_credentials_reported":True,
    }
    fd=os.open(OUT,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,"w") as f:json.dump(report,f,indent=2,sort_keys=True)
    print(json.dumps(report,indent=2,sort_keys=True))
    if not subject_present or not verified:
        raise SystemExit(2)

if __name__=="__main__":main()
