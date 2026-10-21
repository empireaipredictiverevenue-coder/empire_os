"""Bounded UK/US original regulator + official-source preflight, NOT admission.

Reuses Empire Research's existing exact-URL, no-redirect HTTPS HTML inspector,
and a separately pinned Socrata dataset-metadata-only endpoint. No searches,
permit records, names, addresses, scraping discovery, mail, DB or approvals.
"""
from __future__ import annotations

import argparse
from datetime import datetime,timezone
from hashlib import sha256
import json
from pathlib import Path
from urllib.request import Request,build_opener
from urllib.error import HTTPError,URLError
from bs4 import BeautifulSoup

from empire_os.research.brokerage_candidate_source_preflight import _fetch_original_candidate
from empire_os.research.brokerage_editorial_review import _NoRedirect
from empire_os.research.original_source_passages import extract_source_passage_anchors

SOURCES=(
    ("solar","GB","ofgem_export","https://www.ofgem.gov.uk/environmental-and-social-schemes/smart-export-guarantee-seg","html",("solar","export","generation")),
    ("solar","US","illinois_shines","https://ipa.illinois.gov/renewable-resources/illinois-shines-info.html","html",("solar","illinois shines","renewable")),
    ("solar","US","illinois_consumer","https://ipa.illinois.gov/about-ipa/consumer-protection.html","html",("solar","consumer protection","incentive")),
    ("hvac","GB","hse_gas_safe","https://www.hse.gov.uk/gas/gas-safe-register-check.htm","html",("gas safe","engineer","registered")),
    ("hvac","US","illinois_energy_code","https://cdb.illinois.gov/business/codes/illinois-energy-codes/illinois-energy-conservation-code.html","html",("energy","conservation","buildings")),
    ("hvac","US","chicago_codes_redirect","https://chicago.gov/city/en/depts/bldgs/provdrs/bldg_code/svcs/chicago_buildingcodeonline.html","html",("heating","mechanical","construction")),
    ("legal","GB","sra_register_denied","https://www.sra.org.uk/consumers/register/","html",("solicitors","firm","register")),
    ("legal","GB","gov_solicitor_certificate","https://www.gov.uk/find-licences/solicitor-s-practising-certificate-england-wales","html",("solicitor","practising certificate")),
    ("legal","US","illinois_ardc_search","https://iardc.org/Lawyer/Search","html",("lawyer","search","registration")),
    ("legal","US","illinois_courts_licensure","https://www.illinoiscourts.gov/eservices/attorney-licensure/","html",("attorney","licensure","lawyer")),
    ("property","GB","gov_brownfield","https://www.gov.uk/guidance/brownfield-land-registers","html",("brownfield","land","register")),
    ("property","US","chicago_dpd_redirect","https://chicago.gov/dpd","html",("planning","zoning","development")),
    ("property","US","chicago_blockbuilder_redirect","https://chicago.gov/blockbuilder","html",("land","property","development")),
    ("property","US","chicago_dcd_original","https://www.chicago.gov/city/en/depts/dcd.html","html",("planning","development","zoning")),
    ("property","US","chicago_zoning_metadata","https://data.cityofchicago.org/api/views/7cve-jgbp.json","json",()),
)
SCHEMA="empire.research.official_multisector_original_candidates.v1"
DATASET_ID="7cve-jgbp"
JSON_URL="https://data.cityofchicago.org/api/views/7cve-jgbp.json"
HEADING_ONLY_EXPECTED={
    "illinois_ardc_search":"Lawyer Search",
    "illinois_courts_licensure":"Attorney Licensure",
}
MAX_JSON_BYTES=350000
OUTPUT_NAME="RESEARCH_SOLAR_HVAC_LEGAL_PROPERTY_UK_US_OFFICIAL_SOURCES_20261021.json"


def fetch_official_metadata(url:str)->bytes:
    if url!=JSON_URL:
        raise ValueError("UNKNOWN_FIXED_OFFICIAL_DATASET")
    req=Request(url,headers={
        "User-Agent":"EmpireOSOriginalSourceReview/1.0",
        "Accept":"application/json",
    })
    with build_opener(_NoRedirect()).open(req,timeout=10) as response:
        if response.status!=200 or response.geturl()!=url:
            raise ValueError("UNEXPECTED_DATASET_ORIGIN_OR_HTTP")
        if "application/json" not in str(response.headers.get("Content-Type","")).lower():
            raise ValueError("NOT_DATASET_METADATA_JSON")
        blob=response.read(MAX_JSON_BYTES+1)
    if not blob or len(blob)>MAX_JSON_BYTES:
        raise ValueError("DATASET_METADATA_BYTES_OUT_OF_BOUNDS")
    data=json.loads(blob)
    if (not isinstance(data,dict) or data.get("id")!=DATASET_ID
        or not isinstance(data.get("name"),str)
        or not isinstance(data.get("columns"),list)):
        raise ValueError("UNEXPECTED_DATASET_METADATA_ID_OR_SHAPE")
    return blob


def review_candidates(*, html_fetch=_fetch_original_candidate,
                      json_fetch=fetch_official_metadata,
                      when:datetime|None=None)->dict:
    now=when or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("TIMEZONE_AWARE_RESEARCH_OBSERVATION_REQUIRED")
    rows=[]
    for sector,market,label,url,kind,terms in SOURCES:
        row={
            "sector":sector,"market":market,"label":label,
            "exact_source_url":url,"source_kind":kind,
            "observed_at_utc":now.astimezone(timezone.utc).isoformat(),
            "source_admitted":False,
            "source_license_or_reuse_rights_verified":False,
            "official_claim_independently_validated":False,
            "named_business_registration_checked":False,
            "customer_demand_verified":False,
            "individual_property_or_person_records_fetched":0,
            "editorial_owner_signed_off":False,
            "outbound_authorized":False,
            "customer_delivery_authorized":False,
            "db_or_finance_authorized":False,
        }
        try:
            if kind=="html":
                data=html_fetch(url)
                if not isinstance(data,bytes) or not 0<len(data)<=600000:
                    raise ValueError("ORIGINAL_HTML_BYTES_OUT_OF_BOUNDS")
                soup=BeautifulSoup(data,"html.parser")
                title=" ".join(soup.title.get_text(" ",strip=True).split())[:180] if soup.title else ""
                anchors=extract_source_passage_anchors(data,terms=terms)
                if not anchors:
                    expected=HEADING_ONLY_EXPECTED.get(label)
                    heading_only=(expected is not None
                                  and (sector,market)==("legal","US")
                                  and expected.casefold() in title.casefold())
                    row.update({
                        "status":("ORIGINAL_OFFICIAL_HEADING_ONLY_NOT_ADMITTED"
                                  if heading_only else "ORIGINAL_HTML_TOPIC_ANCHOR_HELD"),
                        "source_body_sha256":sha256(data).hexdigest(),
                        "source_body_bytes":len(data),
                        "topic_anchor_count":0,
                        "document_title":title,
                        "substantive_original_passage_verified":False,
                        "source_identity_page_title_only":heading_only,
                    })
                else:
                    row.update({"status":"ORIGINAL_OFFICIAL_HTML_OBSERVED_NOT_ADMITTED",
                                "source_body_sha256":sha256(data).hexdigest(),
                                "source_body_bytes":len(data),
                                "topic_anchor_count":len(anchors),
                                "document_title":title,
                                "bounded_source_anchors":anchors[:3]})
            else:
                if kind!="json":
                    raise ValueError("UNSUPPORTED_SOURCE_FORMAT")
                raw=json_fetch(url)
                if not isinstance(raw,bytes) or not 0<len(raw)<=MAX_JSON_BYTES:
                    raise ValueError("ORIGINAL_METADATA_BYTES_OUT_OF_BOUNDS")
                meta=json.loads(raw)
                if (not isinstance(meta,dict) or meta.get("id")!=DATASET_ID
                    or not isinstance(meta.get("columns"),list)):
                    raise ValueError("UNEXPECTED_ORIGINAL_DATASET_ID")
                row.update({"status":"ORIGINAL_OFFICIAL_METADATA_OBSERVED_NOT_ADMITTED",
                            "source_body_sha256":sha256(raw).hexdigest(),
                            "source_body_bytes":len(raw),
                            "original_dataset_id":DATASET_ID,
                            "declared_column_descriptor_count":len(meta["columns"]),
                            "permit_or_zoning_rows_fetched":0})
        except (HTTPError,URLError,OSError,ValueError,TimeoutError,UnicodeError,TypeError) as error:
            row.update({"status":"ORIGINAL_SOURCE_FETCH_OR_TOPIC_HELD",
                        "hold_reason_type":type(error).__name__})
        rows.append(row)
    matrix=[]
    for niche in ("solar","hvac","legal","property"):
        for market in ("US","GB"):
            subset=[r for r in rows if r["sector"]==niche and r["market"]==market]
            matrix.append({
                "sector":niche,"market":market,
                "candidate_count":len(subset),
                "original_candidates_observed":sum(r["status"] in (
                    "ORIGINAL_OFFICIAL_HTML_OBSERVED_NOT_ADMITTED",
                    "ORIGINAL_OFFICIAL_METADATA_OBSERVED_NOT_ADMITTED",
                    "ORIGINAL_OFFICIAL_HEADING_ONLY_NOT_ADMITTED",
                ) for r in subset),
                "source_admissions":0,
                "research_editorial_approval":False,
            })
    return {
        "schema_version":SCHEMA,
        "status":"BOUNDED_OFFICIAL_ORIGINAL_SOURCE_CANDIDATES_EDITORIAL_HELD",
        "observed_at_utc":now.astimezone(timezone.utc).isoformat(),
        "total_exact_sources_checked":len(rows),
        "original_candidates_observed":sum(r["status"] in (
            "ORIGINAL_OFFICIAL_HTML_OBSERVED_NOT_ADMITTED",
            "ORIGINAL_OFFICIAL_METADATA_OBSERVED_NOT_ADMITTED",
                    "ORIGINAL_OFFICIAL_HEADING_ONLY_NOT_ADMITTED",
        ) for r in rows),
        "held_candidates":sum(r["status"] not in (
            "ORIGINAL_OFFICIAL_HTML_OBSERVED_NOT_ADMITTED",
            "ORIGINAL_OFFICIAL_METADATA_OBSERVED_NOT_ADMITTED",
                    "ORIGINAL_OFFICIAL_HEADING_ONLY_NOT_ADMITTED",
        ) for r in rows),
        "sector_market_matrix":matrix,
        "source_admissions":0,"source_rights_verified":False,
        "independent_editorial_signoffs":0,
        "real_buyer_requests_proven":0,
        "messages_or_customer_actions_sent":0,
        "database_writes":False,
        "money_moved":False,
        "rows":rows,
    }


def main()->None:
    p=argparse.ArgumentParser()
    p.add_argument("--read-only",required=True,action="store_true")
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    root=Path(__file__).resolve().parents[1]
    expected=root/"docs/commercial"/OUTPUT_NAME
    output=args.output.absolute()
    if output!=expected or output.exists() or output.is_symlink():
        raise ValueError("only the exact new sector observation ledger may be written")
    result=review_candidates()
    with output.open("x",encoding="utf-8") as f:
        json.dump(result,f,sort_keys=True,indent=2)
        f.write("\n")
    print(json.dumps({
        "status":result["status"],"checked":result["total_exact_sources_checked"],
        "observed":result["original_candidates_observed"],
        "held":result["held_candidates"],
        "market_pairs_with_at_least_one_observation":sum(
            x["original_candidates_observed"]>=1 for x in result["sector_market_matrix"]),
        "admitted":result["source_admissions"],
        "customer_actions":result["messages_or_customer_actions_sent"],
    },sort_keys=True))


if __name__=="__main__":
    main()
