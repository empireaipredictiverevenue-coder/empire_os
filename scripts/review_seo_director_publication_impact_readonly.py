#!/usr/bin/env python3
"""One-shot SEO Director owner-report from GSC + exact 2026-10-15 receipts.

Reads only fixed first-party loopback services and owned public HTML. No
Google query strings, contact details or raw site HTML persisted. No timer,
affiliate click, CRM write, index request, outbound, payment or paid media.
"""
from __future__ import annotations

import argparse
from datetime import date, timedelta, timezone, datetime
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any, Callable
from urllib.parse import urlsplit

from bs4 import BeautifulSoup
import requests

from empire_os.search_intelligence.organic_revenue_baseline import review_owned_organic_baseline
from empire_os.search_intelligence.seo_publication_impact_review import (
    ORIGIN, PAGE_SET, EXPECTED_HEADINGS, review_publication_impact,
)

API = "http://127.0.0.1:8771/v1/search/search-console"
FOUNDER_API = "http://127.0.0.1:8766/v1/founder-ops/executive-roles/status"
FIRST = Path("/srv/empire_os/runtime/public_website/seo_four_pages_20261015_release_v1/release_receipt.json")
SECOND = Path("/srv/empire_os/runtime/public_website/seo_director_b2b_two_pages_20261015_release_v1/release_receipt.json")
METADATA = Path("/srv/empire_os/runtime/public_website/seo_buyer_metadata_two_pages_20261015_release_v1/release_receipt.json")
TAM_ANSWER = Path("/srv/empire_os/runtime/public_website/seo_tam_answer_one_page_20261015_release_v1/release_receipt.json")
SIX_LINK_RELEASE = Path("/srv/empire_os/runtime/public_website/seo_editorial_six_industry_pages_20261016_v1/release_receipt.json")
ALLOWED_OUTPUT_DIR = Path("/var/tmp")


def _receipt(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 65_536:
        raise ValueError("trusted_publication_receipt_required")
    result=json.loads(path.read_text("utf-8"))
    if not isinstance(result,dict):
        raise ValueError("malformed_publication_receipt")
    return result


def _get_json(getter: Callable[..., Any], url: str, *, params: dict | None = None) -> dict[str, Any]:
    if not (url.startswith(API + "/") or url == FOUNDER_API):
        raise ValueError("outside_fixed_first_party_local_api")
    r=getter(url,params=params,timeout=11,allow_redirects=False,
             headers={"Accept":"application/json", "User-Agent":"EmpireOS-SEO-Director-Release-Observer/1.0"})
    if r.status_code!=200 or len(r.content)>300_000:
        raise ValueError("first_party_readonly_api_unavailable")
    packet=r.json()
    if not isinstance(packet,dict):
        raise ValueError("unexpected_first_party_api_payload")
    return packet


def _read_public_page(getter: Callable[..., Any], path: str) -> dict[str, Any]:
    if path not in PAGE_SET:
        raise ValueError("out_of_scope_page")
    r=getter(ORIGIN + path, timeout=9, allow_redirects=False,
             headers={"User-Agent":"EmpireOS-SEO-Director-Release-Observer/1.0"})
    if r.status_code!=200 or len(r.content)>250_000 or "text/html" not in r.headers.get("Content-Type", ""):
        raise ValueError("public_html_not_available")
    page=BeautifulSoup(r.text,"html.parser")
    h2=[x.get_text(" ",strip=True) for x in page.select("main h2")]
    canonical=[x.get("href") for x in page.select('link[rel="canonical"]')]
    form=page.select_one('main form')
    expected=EXPECTED_HEADINGS[path]
    business_url="/trust" if path=="/commercial" else "/commercial"
    return {
        "http":r.status_code,
        "sha256":hashlib.sha256(r.content).hexdigest(),
        "canonical":canonical[0] if len(canonical)==1 else None,
        "h1_count":len(page.select("h1")),
        "expected_buyer_heading_visible":expected in h2,
        "approved_internal_business_link_present":bool(page.select(f'a[href="{business_url}"]')),
        "noindex":any('noindex' in (str(meta.get('content') or '').lower())
                      for meta in page.select('meta[name="robots"]')),
        "required_consent_checkbox":bool(form and form.select_one('input[type="checkbox"][required]')),
        "privacy_link_inside_form":bool(form and form.select_one('a[href="/privacy"]')),
    }


def _windows(end: date) -> tuple[date,date,date,date]:
    if not date(2026,10,13) <= end <= date.today():
        raise ValueError("unbounded_or_unavailable_gsc_date")
    start=end-timedelta(days=28)
    prior_end=start-timedelta(days=1)
    prior_start=prior_end-timedelta(days=28)
    return start,end,prior_start,prior_end


def run(*, getter: Callable[..., Any] = requests.get,
        end: date | None = None,
        first: Path = FIRST, second: Path = SECOND,
        metadata: Path = METADATA,
        tam_answer: Path = TAM_ANSWER,
        six_link_release: Path = SIX_LINK_RELEASE) -> dict[str, Any]:
    # Search Console normally requires processing time; never demand today's
    # unprocessed rows or interpret absence of today's data as no traffic.
    today=datetime.now(timezone.utc).date()
    until=end or today-timedelta(days=2)
    start,until,earlier,earlier_until=_windows(until)
    def query(kind: str, a: date, b: date) -> dict[str, Any]:
        return _get_json(getter, API+"/"+kind,params={
            "start_date":a.isoformat(),"end_date":b.isoformat(),
            "limit":999 if kind=="observations" else 90,
        })
    current=query('observations',start,until)
    previous=query('observations',earlier,earlier_until)
    daily_current=query('daily',start,until)
    daily_previous=query('daily',earlier,earlier_until)
    baseline=review_owned_organic_baseline(
        site_url="sc-domain:empire-ai.co.uk",tenant_id="empire-ai",
        site_id="empire-ai.co.uk",current=current,previous=previous,
        current_daily=daily_current,previous_daily=daily_previous,
        current_start=start.isoformat(),current_end=until.isoformat(),
        previous_start=earlier.isoformat(),previous_end=earlier_until.isoformat(),
    )
    owned={path:_read_public_page(getter,path) for path in PAGE_SET}
    # Buyer capacity is classification only. Never request raw customer rows.
    try:
        f=_get_json(getter,FOUNDER_API)
        status=f.get('business_development',{}).get('downstream_buyer_capacity',{}).get('status')
        if status not in ('NO_VERIFIED_COMMERCIAL_CAPACITY','VERIFIED_COMMERCIAL_CAPACITY'):
            status='UNKNOWN_NOT_VERIFIED'
    except (requests.RequestException,ValueError,TypeError,AttributeError):
        status='UNKNOWN_NOT_VERIFIED'
    www=getter("https://www.empire-ai.co.uk/",timeout=9,allow_redirects=False,
               headers={"User-Agent":"EmpireOS-SEO-Director-Release-Observer/1.0"})
    if www.status_code not in (200,301,308):
        raise ValueError('unknown_www_canonical_response')
    roof=getter(ORIGIN+'/roofing',timeout=9,allow_redirects=False,
              headers={"User-Agent":"EmpireOS-SEO-Director-Release-Observer/1.0"})
    if roof.status_code!=200 or 'noindex' not in (roof.text+str(roof.headers.get('X-Robots-Tag',''))).lower():
        raise ValueError('protected_consumer_roofing_noindex_not_proven')
    result=review_publication_impact(
        baseline=baseline,observed_query_pages=current,
        earlier_release=_receipt(first),latest_release=_receipt(second),
        metadata_release=_receipt(metadata) if metadata.is_file() else None,
        tam_answer_release=_receipt(tam_answer) if tam_answer.is_file() else None,
        industry_link_release=_receipt(six_link_release) if six_link_release.is_file() else None,
        live_pages=owned,buyer_capacity_status=status,
        www_status=www.status_code,
    )
    return {**result,'buyer_roofing_noindex_held':True,
            'source_receipts_readonly_verified':True,
            'raw_google_queries_persisted':False,
            'raw_html_persisted':False,
            'founder_contact_data_read':False}


def write_private_once(result:dict[str,Any], path:Path,
                       allowed_root:Path=ALLOWED_OUTPUT_DIR) -> None:
    root=allowed_root.resolve()
    if (path.is_symlink() or path.parent.resolve()!=root
        or not re.fullmatch(r'empire_seo_director_postrelease_[0-9]{8}\.json',path.name)):
        raise ValueError('bounded_private_observation_filename_required')
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o600)
    try:
        with os.fdopen(fd,'w') as f:
            json.dump(result,f,sort_keys=True,indent=2)
            f.write('\n');f.flush();os.fsync(f.fileno())
    except Exception:
        path.unlink(missing_ok=True)
        raise


def main():
    parser=argparse.ArgumentParser(description='First-party SEO Council publication outcome review')
    parser.add_argument('--review-only',action='store_true',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    try:
        result=run()
        write_private_once(result,args.output)
    except Exception as exc:
        # No exception body, provider URLs, query strings, or customer IDs.
        print(json.dumps({'status':'EVIDENCE_HOLD','reason_code':type(exc).__name__,
                         'site_modified':False,'paid_media_spend_authorized':False,
                         'execution_authority':'none'},sort_keys=True))
        return 2
    print(json.dumps(result,sort_keys=True))
    return 0

if __name__=='__main__':
    raise SystemExit(main())
