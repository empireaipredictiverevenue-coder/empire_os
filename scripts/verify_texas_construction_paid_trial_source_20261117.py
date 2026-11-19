"""Bounded Dallas paid-trial fit verification for the ORIGINAL EmpireOS brokerage.

One official Socrata dataset, November 2026, <=40 issuance rows, no scraping
of company/contact details and no CRM/customer/delivery writes.
This is an internal qualification read, NOT a citywide or lead feed.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import argparse
import json
import re

import requests

URL = "https://www.dallasopendata.com/resource/e7gq-4sah.json"
SOURCE_PAGE = "https://www.dallasopendata.com/Services/Building-Permits/e7gq-4sah"
PERMIT_TYPE = "Commercial New Construction Permit"
WHERE = "issued_date like '11/%/26' and permit_type = 'Commercial New Construction Permit'"
def where_for_month(month: str) -> str:
    """A month is a validated YYYY-MM period, never arbitrary source SQL."""
    if not re.fullmatch(r"20[0-9]{2}-(0[1-9]|1[0-2])", month):
        raise ValueError("DALLAS_MONTH_INVALID")
    year, mon = month.split("-")
    return (f"issued_date like '{mon}/%/{year[2:]}'"
            " and permit_type = 'Commercial New Construction Permit'")
FIELDS = "permit_number,permit_type,issued_date,land_use,work_description,value,area,contractor"
CAP = 40
IDENTITY = re.compile(r"[A-Za-z0-9_.-]{5,80}\Z")
CLASSIFICATION_TOKENS = {
    "HOTEL_TEXT_MENTION": re.compile(r"\b(?:hotel|motel|hospitality)\b", re.I),
    "MULTIFAMILY_TEXT_MENTION": re.compile(r"\b(?:apartments?|multi[- ]?family|mixed[- ]?use)\b", re.I),
    "FITNESS_TEXT_MENTION": re.compile(r"\b(?:fitness|gymnasium|gym)\b", re.I),
}

def assess(rows: list[dict], *, now: datetime, total: int,
           sample_sha: str, count_sha: str, month: str = "2026-11") -> dict:
    if now.utcoffset() is None or not isinstance(rows,list) or not isinstance(total,int):
        raise ValueError("SOURCE_SCHEMA_OR_CLOCK_INVALID")
    where_for_month(month)
    year, mon = map(int, month.split("-"))
    if (year,mon) > (now.year,now.month):
        raise ValueError("FUTURE_DALLAS_SOURCE_MONTH")
    if (not 0 <= len(rows) == total <= CAP
        or not re.fullmatch(r"[0-9a-f]{64}",sample_sha)
        or not re.fullmatch(r"[0-9a-f]{64}",count_sha)):
        raise ValueError("BOUND_OR_RECEIPT_MISMATCH")
    accepted = set(FIELDS.split(","))
    seen = set()
    counts = Counter()
    mentions = Counter()
    dates = []
    internal_candidates = []
    for item in rows:
        if not isinstance(item,dict) or not set(item).issubset(accepted):
            raise ValueError("UNEXPECTED_DALLAS_FIELDS")
        ref = item.get("permit_number")
        if not isinstance(ref,str) or not IDENTITY.fullmatch(ref) or ref in seen:
            raise ValueError("UNVERIFIED_OR_DUPLICATE_PERMIT_REF")
        seen.add(ref)
        if item.get("permit_type") != PERMIT_TYPE:
            raise ValueError("NOT_COMMERCIAL_NEW_CONSTRUCTION")
        date_str = item.get("issued_date")
        if not isinstance(date_str,str) or not re.fullmatch(r"[0-9]{2}/[0-9]{2}/[0-9]{2}",date_str):
            raise ValueError("ISSUE_DATE_SOURCE_FORMAT_INVALID")
        try:
            issue=datetime.strptime(date_str,"%m/%d/%y").replace(tzinfo=timezone.utc)
        except ValueError as err:
            raise ValueError("INVALID_ISSUED_DATE") from err
        if issue.date() > now.date() or issue.year!=year or issue.month!=mon:
            raise ValueError("FUTURE_OR_WRONG_PERIOD_PERMIT")
        dates.append(issue.date().isoformat())
        for field in accepted:
            if isinstance(item.get(field),str) and item[field].strip():
                counts[field]+=1
        land_use=item.get("land_use")
        if land_use is not None and (
            not isinstance(land_use,str)
            or not re.fullmatch(r"[A-Za-z0-9 /&(),.+_-]{1,100}",land_use)
        ):
            raise ValueError("UNTRUSTED_LAND_USE")
        description=item.get("work_description") or ""
        if not isinstance(description,str) or len(description)>4000:
            raise ValueError("UNTRUSTED_DESCRIPTION")
        matched=[label for label,pattern in CLASSIFICATION_TOKENS.items()
                 if pattern.search(description)]
        for label in matched:
            mentions[label]+=1
        if matched:
            internal_candidates.append({
                "source_permit_reference":ref,
                "source_reported_date":issue.date().isoformat(),
                "description_keyword_flags_not_verified_project_types":matched,
                "official_land_use_field":item.get("land_use") or None,
                "source_dataset":SOURCE_PAGE,
                "developer_verified":False,
                "current_construction_stage_verified":False,
                "specifier_or_decision_maker_verified":False,
                "gym_requirement_verified":False,
                "outreach_authorised":False,
            })
    internal_candidates.sort(
        key=lambda x:(x["source_reported_date"],x["source_permit_reference"]),reverse=True
    )
    return {
        "schema_version":"empire.data_brokerage.texas_dallas_pilot.v1",
        "status":"SOURCE_VALIDATED_COMMERCIAL_BUYER_FIT_NOT_VERIFIED",
        "execution_authority":"none",
        "source_url":SOURCE_PAGE,
        "source_api_url":URL,
        "period":month,
        "observed_at":now.astimezone(timezone.utc).isoformat(),
        "source_response_sha256":sample_sha,
        "source_count_response_sha256":count_sha,
        "bounded_query_total":total,
        "rows_accepted":len(rows),
        "source_rows_complete_for_filter":total<CAP,
        "source_field_presence":dict(sorted(counts.items())),
        "source_reported_dates":dict(sorted(Counter(dates).items())),
        "actual_issuance_status_verified":False,
        "text_mentions_not_verified_classification":dict(sorted(mentions.items())),
        "internal_keyword_candidates":internal_candidates[:8],
        "unreviewed_keyword_matches":max(0,len(internal_candidates)-8),
        "requested_texas_project_area_supported":"DALLAS_CITY_ONLY",
        "other_texas_jurisdictions_covered":False,
        "project_hotel_apartment_mix_verified":False,
        "developer_or_owner_verified":False,
        "start_completion_dates_verified":False,
        "active_build_stage_verified":False,
        "architect_general_contractor_verified":False,
        "decision_maker_identity_verified":False,
        "contact_permission_verified":False,
        "fitness_facility_verified":False,
        "buyer_budget_or_order_verified":False,
        "source_reuse_rights_cleared":False,
        "crm_write":False,
        "outreach_sent":False,
        "customer_delivery_enabled":False,
    }

def fetch_and_assess(*, now:datetime, session=requests,
                     month: str = "2026-11", timeout: int = 15) -> dict:
    query = where_for_month(month)
    if not 1 <= timeout <= 15:
        raise ValueError("SOURCE_READ_TIMEOUT_OUT_OF_BOUNDS")
    params={"$select":FIELDS,"$where":query,"$limit":CAP}
    count_params={"$select":"count(*) as n","$where":query}
    output=[]
    for request_params in (params,count_params):
        reply=session.get(URL,params=request_params,timeout=timeout,
                          headers={"Accept":"application/json"},allow_redirects=False)
        if reply.status_code!=200 or len(reply.content)>160_000:
            raise ValueError("UNAVAILABLE_OR_OVERSIZE_DALLAS_RESPONSE")
        try:
            records=json.loads(reply.content)
        except (ValueError,UnicodeError) as err:
            raise ValueError("INVALID_OFFICIAL_RESPONSE") from err
        if not isinstance(records,list):
            raise ValueError("SOURCE_RETURNED_NONLIST")
        output.append((records,sha256(reply.content).hexdigest()))
    rows,digest=output[0]
    count_rows,count_digest=output[1]
    if (len(count_rows)!=1 or not isinstance(count_rows[0],dict)
        or not str(count_rows[0].get("n","")).isdigit()):
        raise ValueError("OFFICIAL_COUNT_NOT_VERIFIED")
    return assess(rows,now=now,total=int(count_rows[0]["n"]),
                  sample_sha=digest,count_sha=count_digest,month=month)

def format_report(result:dict) -> str:
    def field(name):
        return result["source_field_presence"].get(name,0)
    def code_list(rows):
        return "\n".join(
            f"| `{r['source_permit_reference']}` | {r['source_reported_date']} | "
            f"{', '.join(r['description_keyword_flags_not_verified_project_types'])} | "
            f"{str(r['official_land_use_field'] or 'UNKNOWN')} |"
            for r in rows
        ) or "| No keyword-flagged examples | — | — | — |"
    n=result["rows_accepted"]
    return f"""# Dallas construction intelligence — bounded buyer-trial evidence

**Owner:** Existing EmpireOS Data Brokerage / Sales Director
**Research timestamp (UTC):** {result['observed_at']}
**Authority:** Internal research only. No outreach, CRM write, sale or customer delivery.

## Official source acceptance

Dataset: City of Dallas [Building Permits]({SOURCE_PAGE}), API: {URL}. Period filter: November 2026, permit type **Commercial New Construction Permit**. Exact query is limited to {CAP} records and cross-checked against an official count query.

**Accepted permit records (NOT independently confirmed issued):** {n}. **Query total:** {result['bounded_query_total']}. Source filter complete within the {CAP}-row cap: **{result['source_rows_complete_for_filter']}** (not comprehensive Dallas project coverage). Earliest/latest dates as labelled 'issued_date' in this source (actual issuance not verified): {min(result['source_reported_dates'],default='N/A')} / {max(result['source_reported_dates'],default='N/A')}. No work-description, owner, contractor or address content has been exported.

**Official source receipts:** row-response SHA256 `{result['source_response_sha256']}`; count-response SHA256 `{result['source_count_response_sha256']}`.

### Field completeness — a permit reference is not a qualified buyer lead

| Source field | Nonempty among {n} permits |
|---|---:|
| Official permit number | {field('permit_number')} |
| Source field issued_date (not proof of issuance) | {field('issued_date')} |
| Work description (used only for in-memory keyword flags) | {field('work_description')} |
| Official land-use category | {field('land_use')} |
| Contractor field (not exported) | {field('contractor')} |
| Reported project valuation | {field('value')} |
| Area | {field('area')} |

**Text-keyword flags, not independently verified project types:** {result['text_mentions_not_verified_classification']}.

### Private research leads to verify (NOT qualified prospects)

Only permit reference, source-reported date and in-memory text keyword classifications are retained. The source field name 'issued_date' does NOT independently confirm issuance. The original text, people, companies and addresses are not exported. Every interpretation is **unverified**.

| Official permit reference | Issue date | Unverified description keywords | Official land-use class |
|---|---|---|---|
{code_list(result['internal_keyword_candidates'])}

## Comparison to the buyer's published paid-trial scope

- **Pass:** Official city-level permit IDs, verified original issue dates, source link, typed commercial-new-construction permits, capped source receipts.
- **Partial / inferred:** Hotel/apartment/mixed-use keyword matches from source work descriptions. These do NOT establish actual project use or gym specification.
- **Fail / absent:** Developer identity, owner/company verification, decision-maker name/contact, construction start and finish dates, current execution stage, architect/general contractor confirmation, planned fitness facility, qualified opportunity ranking, and sustainable weekly enrichment.
- **Scope mismatch:** Dallas city records are not all of Texas; the public Upwork notice does not specify Dallas exclusively, and the request's buyer identity, active order state and authorisation to contact are not independently verified.
- **Source reuse:** Dallas OpenData has a portal terms-of-use agreement; external commercial redistribution and use of specific fields remain held pending the existing owner rights review.
- **Outcome:** `SOURCE_VALIDATED_COMMERCIAL_BUYER_FIT_NOT_VERIFIED`. Not suitable to claim fulfilment of the buyer's paid trial. This demonstrates a meaningful new Texas research source, not a commissioned customer pilot.

**Commercial next evidence:** Obtain a real buyer's exact city, hotel/apartment criteria, decision-stage questions, project identity requirements, licence terms, and acceptance tests; match a further independently verified project-specific source before proposing external delivery. No application, message, spreadsheet delivery or payment taken.
"""

def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--write-internal-report",action="store_true")
    args=parser.parse_args()
    result=fetch_and_assess(now=datetime.now(timezone.utc))
    safe={
        k:v for k,v in result.items()
        if k not in ("internal_keyword_candidates",)
    }
    print(json.dumps(safe,sort_keys=True))
    if args.write_internal_report:
        path=Path("/srv/empire_os/docs/commercial/US_CONSTRUCTION_TEXAS_DALLAS_PAID_TRIAL_EVIDENCE_20261117.md")
        if path.exists() or path.is_symlink():
            raise ValueError("EXISTING_INTERNAL_EVIDENCE_REFUSE_OVERWRITE")
        path.write_text(format_report(result),encoding="utf-8")
        path.chmod(0o600)
        print("INTERNAL_REPORT_CREATED",path)
    return 0

if __name__=="__main__":
    raise SystemExit(main())
