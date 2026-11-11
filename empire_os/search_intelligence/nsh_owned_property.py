"""Add the owned National Storm Hub GSC property to the ORIGINAL search reader.

No second service or changed Empire AI property binding, OAuth scope or sender.
Never claim live Google access merely because the founder verified her/his own
separate property: the *existing service account* must have explicit access.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any
from urllib.parse import urlsplit

import requests
from fastapi import APIRouter, HTTPException, Query, Response

from .search_console import GoogleSearchConsoleAdapter, SearchConsoleUnavailable, configured_search_console_adapter

NSH_SITE = "sc-domain:nationalstormhub.com"
EXISTING_SITE = "sc-domain:empire-ai.co.uk"
SITES_URL = "https://searchconsole.googleapis.com/webmasters/v3/sites"
PERMITTED_ROLES = frozenset(("siteOwner", "siteFullUser", "siteRestrictedUser"))
router = APIRouter(prefix="/v1/search/search-console/national-storm-hub", tags=["national-storm-hub-gsc"])


def _read_authenticated_nsh() -> GoogleSearchConsoleAdapter:
    """Check the real account-level GSC grant; fail closed, no data leaks."""
    primary = configured_search_console_adapter()
    status = primary.status()
    if (not isinstance(primary, GoogleSearchConsoleAdapter)
        or not status.available or primary.site_url != EXISTING_SITE):
        raise SearchConsoleUnavailable("primary_gsc_owner_not_ready")
    # This is the existing approved read-only token, never a new credential.
    try:
        token = primary._token_provider(primary.credential_file)
    except Exception as exc:
        raise SearchConsoleUnavailable("gsc_existing_credential_unavailable") from exc
    if not isinstance(token, str) or not token:
        raise SearchConsoleUnavailable("gsc_token_unavailable")
    try:
        response = requests.get(
            SITES_URL,
            headers={"Authorization":"Bearer "+token,"Accept":"application/json"},
            timeout=18,
        )
        response.raise_for_status()
        payload=response.json()
    except (requests.RequestException, ValueError) as exc:
        raise SearchConsoleUnavailable("gsc_property_access_check_failed") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("siteEntry", []), list):
        raise SearchConsoleUnavailable("gsc_property_listing_invalid")
    matched=[s for s in payload.get("siteEntry", []) if isinstance(s,dict)
             and s.get("siteUrl")==NSH_SITE and s.get("permissionLevel") in PERMITTED_ROLES]
    if len(matched)!=1:
        raise SearchConsoleUnavailable("nsh_property_not_granted_to_existing_service_account")
    return GoogleSearchConsoleAdapter(
        NSH_SITE,primary.credential_file,
        token_provider=primary._token_provider,post_json=primary._post_json,
    )


@router.get("/status")
def nsh_status(response:Response)->dict[str,Any]:
    response.headers["Cache-Control"]="no-store"
    response.headers["X-Content-Type-Options"]="nosniff"
    try:
        _read_authenticated_nsh()
        available=True;reason="ready"
    except (SearchConsoleUnavailable,OSError,ValueError,TypeError):
        available=False;reason="nsh_service_account_permission_or_source_unavailable"
    return {
        "site_url":NSH_SITE,"source":"google_search_console",
        "mode":"OBSERVE","credential_scope":"webmasters.readonly",
        "available":available,"reason":reason,
        "original_empire_ai_property":EXISTING_SITE,
        "original_empire_ai_property_binding_changed":False,
        "google_indexation_verified":False,"outbound_authorized":False,
    }


@router.get("/pages")
def nsh_pages(start_date:date,end_date:date,response:Response,
              limit:int=Query(default=100,ge=1,le=1000))->dict[str,Any]:
    response.headers["Cache-Control"]="no-store"
    response.headers["X-Content-Type-Options"]="nosniff"
    if end_date<start_date or end_date-start_date>timedelta(days=31):
        raise HTTPException(status_code=422,detail="invalid_finalized_window")
    try:
        adapter=_read_authenticated_nsh()
        rows=[dict(r) for r in adapter.page_observations(
            start_date=start_date.isoformat(),end_date=end_date.isoformat(),limit=limit)]
    except (SearchConsoleUnavailable,requests.RequestException,ValueError,OSError):
        raise HTTPException(status_code=503,detail="nsh_gsc_property_or_source_unavailable",
                            headers={"Cache-Control":"no-store"}) from None
    if len(rows)>limit or any(not isinstance(r.get("keys"), (tuple,list))
        or len(r["keys"])!=1 or not isinstance(r["keys"][0],str)
        or urlsplit(r["keys"][0]).scheme!="https"
        or urlsplit(r["keys"][0]).netloc!="nationalstormhub.com"
        for r in rows):
        raise HTTPException(status_code=503,detail="nsh_gsc_page_scope_untrusted",
                            headers={"Cache-Control":"no-store"})
    return {
        "site_url":NSH_SITE,"source":"google_search_console",
        "dimensions":["page"],"data_state":"final","mode":"OBSERVE",
        "window":[start_date.isoformat(),end_date.isoformat()],
        "count":len(rows),"items":rows,
        "google_indexation_verified":False,"attributed_buyer_verified":False,
        "revenue_verified":False,"original_property_binding_changed":False,
        "outbound_authorized":False,
    }
