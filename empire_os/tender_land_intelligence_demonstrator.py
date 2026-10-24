"""CA18567 private Land Intelligence sample within original EmpireOS tender lane.

Bounded, curated publicly documented examples. NO live scraping, GIS claims,
legal title checks, supplier eligibility, bidding, CRM/DB or external action.
"""
from __future__ import annotations

from datetime import datetime, timezone
from html import escape
import json
import os
from pathlib import Path
import stat
import tempfile

SCHEMA = "empire.tender_land_intelligence_demonstrator.v1"
OUT_DIR = Path("runtime/acquisition_research")
JSON_NAME = "ca18567_land_intelligence_demo_latest.json"
HTML_NAME = "ca18567_land_intelligence_demo_latest.html"

# Verbatim-length facts paraphrased from official publisher pages, not a
# dataset licence to republish maps or a proof of land availability/title.
PUBLIC_EXAMPLES = (
    {
        "id": "NI-BEL-001",
        "name": "Weavers Cross",
        "area": "Belfast",
        "jurisdiction": "Northern Ireland",
        "kind": "DEVELOPMENT_LAND",
        "evidence_class": "PUBLISHED_DEVELOPMENT_OPPORTUNITY",
        "published_fact": "Belfast City Council describes approximately eight acres of developable land around Grand Central Station, with outline planning permission and sites described as available from summer 2026.",
        "source": "https://www.belfastcity.gov.uk/investinbelfast/investment-opportunities/weavers-cross",
        "source_publisher": "Belfast City Council",
        "planning": "OUTLINE_PERMISSION_PUBLISHED_NOT_INDEPENDENTLY_RECHECKED",
        "current_availability": "UNVERIFIED",
        "title": "UNVERIFIED",
        "landowner_permission": "UNVERIFIED",
        "gis_geometry": "UNVERIFIED",
        "licensing": "PAGE_REFERENCE_ONLY_NO_MAP_REPUBLICATION",
        "next_validation": "Confirm site-by-site parcel boundaries, development phase, current marketing terms, planning reference, legal interest and promoter permission.",
    },
    {
        "id": "NI-BEL-002",
        "name": "Giant's Park CleanTech",
        "area": "Belfast",
        "jurisdiction": "Northern Ireland",
        "kind": "DEVELOPMENT_LAND",
        "evidence_class": "PUBLISHED_SERVICED_SITE_OPPORTUNITY",
        "published_fact": "Belfast City Council describes a roughly 30-acre CleanTech park within North Foreshore, with serviced sites advertised up to 13 acres and a masterplan prepared.",
        "source": "https://www.belfastcity.gov.uk/investinbelfast/investment-opportunities/giant-s-park-environmental-resource-park",
        "source_publisher": "Belfast City Council",
        "planning": "MASTERPLAN_PUBLISHED_NOT_PERMISSION_CONFIRMED",
        "current_availability": "UNVERIFIED",
        "title": "UNVERIFIED",
        "landowner_permission": "UNVERIFIED",
        "gis_geometry": "UNVERIFIED",
        "licensing": "PAGE_REFERENCE_ONLY_NO_MAP_REPUBLICATION",
        "next_validation": "Request current plot schedule, land remediation/flood/ground-risk data, utilities capacity and approved land-use conditions from the site promoter.",
    },
    {
        "id": "ROI-LOU-001",
        "name": "Dundalk Advance Office Building",
        "area": "Dundalk, County Louth",
        "jurisdiction": "Republic of Ireland",
        "kind": "EXISTING_BUILDING",
        "evidence_class": "PUBLISHED_BUILDING_EXCLUDE_FROM_VACANT_LAND",
        "published_fact": "IDA Ireland markets a roughly 3,273 m2 office building on a roughly 1.7 ha site at Finnabair Business Park, beside the M1. This is an existing office building, NOT evidence of a vacant investment-land parcel.",
        "source": "https://www.idaireland.com/scale-with-ida/properties/list/dundalk-advanced-office-building",
        "source_publisher": "IDA Ireland",
        "planning": "SITE_SPECIFIC_PLANNING_NOT_CHECKED",
        "current_availability": "PUBLISHER_LISTS_AVAILABLE_NOT_INDEPENDENTLY_VERIFIED",
        "title": "UNVERIFIED",
        "landowner_permission": "UNVERIFIED",
        "gis_geometry": "UNVERIFIED",
        "licensing": "PAGE_REFERENCE_ONLY_NO_IMAGE_REPUBLICATION",
        "next_validation": "Treat as excluded property comparator unless the buyer's full RFQ explicitly covers existing business premises.",
    },
    {
        "id": "ROI-LOU-002",
        "name": "The Mell, North Drogheda",
        "area": "Drogheda, County Louth",
        "jurisdiction": "Republic of Ireland",
        "kind": "HISTORICAL_LANDBANK",
        "evidence_class": "HISTORICAL_ACQUISITION_NOT_MARKETED_AVAILABILITY",
        "published_fact": "IDA Ireland reported in October 2022 that it acquired adjoining land at The Mell, North Drogheda. The release does NOT establish current land parcels, sale availability or permitted investment uses.",
        "source": "https://www.idaireland.com/latest-news/press-release/ida-ireland-acquires-site-in-north-drogheda-from-louth-county-council",
        "source_publisher": "IDA Ireland",
        "planning": "UNVERIFIED",
        "current_availability": "UNVERIFIED",
        "title": "UNVERIFIED",
        "landowner_permission": "UNVERIFIED",
        "gis_geometry": "UNVERIFIED",
        "licensing": "PAGE_REFERENCE_ONLY_NO_MAP_REPUBLICATION",
        "next_validation": "Ask IDA Ireland for current site/marketing status; obtain current zoning, parcel boundary, servicing and legally shareable ownership detail if permitted.",
    },
)

REGISTRY = (
    {
        "publisher": "Dublin Belfast Economic Corridor partnership",
        "url": "https://www.dbec.info/partners/",
        "purpose": "Eight councils and two university partners; regional coordination only",
        "reuse_status": "LINK_REFERENCE_ONLY",
    },
    {
        "publisher": "OpenDataNI",
        "url": "https://www.nidirect.gov.uk/services/opendatani-portal",
        "purpose": "Northern Ireland open government datasets; licence must be checked per dataset",
        "reuse_status": "DATASET_RIGHTS_PENDING",
    },
    {
        "publisher": "MyPlan Ireland",
        "url": "https://www.myplan.ie/",
        "purpose": "ROI planning map / zoning discovery; per-layer reuse verification required",
        "reuse_status": "DATASET_RIGHTS_PENDING",
    },
    {
        "publisher": "Tailte Eireann",
        "url": "https://tailte.ie/map-shop/map-licences-and-copyright/",
        "purpose": "Mapping and copyright/licensing guidance; publication rights not assumed",
        "reuse_status": "PERMISSION_REQUIRED_IF_REPRODUCING_RESTRICTED_MAPPING",
    },
)

def _private_directory(root: Path) -> Path:
    root = root.resolve(strict=True)
    folder = root / OUT_DIR
    st = folder.lstat()
    if (not stat.S_ISDIR(st.st_mode) or folder.is_symlink()
            or stat.S_IMODE(st.st_mode) != 0o700 or st.st_uid != os.geteuid()):
        raise ValueError("REQUIRES_EXISTING_PRIVATE_EMPIREOS_RESEARCH_DIRECTORY")
    return folder


def _atomic_private(target: Path, payload: str) -> None:
    if target.is_symlink() or (target.exists() and (
        not target.is_file() or stat.S_IMODE(target.stat().st_mode) != 0o600
        or target.stat().st_uid != os.geteuid()
    )):
        raise ValueError("UNSAFE_PRIVATE_DEMO_TARGET")
    fd, tmp = tempfile.mkstemp(prefix=".ca18567-demo-", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            os.fchmod(fh.fileno(), 0o600)
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, target)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def build_report(now: datetime | None = None) -> dict:
    clock = now or datetime.now(timezone.utc)
    if clock.tzinfo is None:
        raise ValueError("TIMEZONE_REQUIRED")
    sites = []
    for source in PUBLIC_EXAMPLES:
        item = dict(source)
        item["source_retrieval_review_date"] = "2026-10-24"
        item["not_verified"] = [
            "current_market_availability",
            "individual_parcel_geometry",
            "legal_title_and_encumbrances",
            "planning_conditions_and_current_status",
            "services_environment_and_infrastructure",
            "economic_viability_and_current_market_price",
            "map_and_commercial_reuse_rights",
            "named_professional_signoff",
        ]
        item["investment_recommendation"] = "NOT_EVALUATED"
        item["ready_for_investor_guide"] = False
        item["definitive_availability"] = False
        item["qualified_professional_review"] = False
        sites.append(item)
    return {
        "schema_version": SCHEMA,
        "observed_at_utc": clock.astimezone(timezone.utc).isoformat(),
        "status": "PRIVATE_SOURCE_CITED_METHOD_SAMPLE_NOT_BID_EVIDENCE",
        "tender_ref": "CA18567",
        "rfq_authenticated": False,
        "buyer_scope_confirmed": False,
        "supplier_credentials_verified": False,
        "scoring_subcriteria_verified": False,
        "delivery_team_committed": False,
        "land_title_verified_count": 0,
        "investment_ready_sites": 0,
        "published_examples": sites,
        "source_registry": list(REGISTRY),
        "data_last_manual_reviewed": "2026-10-24",
        "publication_permission": False,
        "external_data_fetched_by_script": False,
        "map_layers_used": False,
        "public_deployment": False,
        "crm_writes": False,
        "db_writes": False,
        "outbound_sent": False,
        "bid_authorized": False,
        "revenue_verified": False,
        "next_action": "VERIFY_RFQ_AND_SPECIALIST_TEAM; HUMAN_CHECK_EACH_SITE_BEFORE_GUIDE",
    }


def render_html(report: dict, gis_snapshot: dict | None = None) -> str:
    sites = report["published_examples"]
    def e(value: object) -> str:
        return escape(str(value), quote=True)
    rows = []
    for s in sites:
        mark = "Exclude from land list" if s["kind"] == "EXISTING_BUILDING" else (
            "Historical watchlist" if s["kind"] == "HISTORICAL_LANDBANK" else
            "Research candidate — no investment clearance"
        )
        rows.append(
            '<article class="site" data-area="' + e(s["jurisdiction"]) +
            '" data-kind="' + e(s["kind"]) + '">'
            '<div class="meta"><span>' + e(s["id"]) + '</span><span>' +
            e(s["jurisdiction"]) + '</span></div>'
            '<h3>' + e(s["name"]) + '</h3>'
            '<div class="category">' + e(mark) + '</div>'
            '<p>' + e(s["published_fact"]) + '</p>'
            '<div class="evidence"><strong>Source:</strong> <a target="_blank" rel="noopener noreferrer" href="' +
            e(s["source"]) + '">' + e(s["source_publisher"]) + ' ↗</a></div>'
            '<div class="evidence"><strong>Planning evidence:</strong> ' + e(s["planning"]) + '</div>'
            '<div class="evidence"><strong>Current availability:</strong> ' + e(s["current_availability"]) + '</div>'
            '<div class="risk"><strong>Not verified:</strong> title • parcel geometry • utilities • pricing • land rights • specialist sign-off</div>'
            '<details><summary>Next due-diligence action</summary><p>' + e(s["next_validation"]) + '</p></details>'
            '</article>'
        )
    links = "".join(
        '<li><a href="' + e(item["url"]) + '" target="_blank" rel="noopener noreferrer">' +
        e(item["publisher"]) + ' ↗</a> — ' + e(item["purpose"]) + ' (' + e(item["reuse_status"]) + ')</li>'
        for item in report["source_registry"]
    )
    gis_content = '<p>No official GIS samples attached yet. Screening requires a separately authorised geometry and specialist assessment.</p>'
    if isinstance(gis_snapshot, dict) and gis_snapshot.get("schema_version") == "empire.tender_ca18567_official_gis_evidence.v1":
        gis_rows = []
        from empire_os.tender_land_gis_evidence import SOURCES
        for layer in gis_snapshot.get("layers", [])[:2]:
            if not isinstance(layer, dict):
                continue
            official = SOURCES.get(layer.get("source_id"))
            if (official is None or layer.get("catalogue") != official["catalogue"]
                or layer.get("licence") != official["licence"]
                or layer.get("status") != "OFFICIAL_GIS_SAMPLE_OBSERVED_NOT_PARCEL_SCREENING"
                or not isinstance(layer.get("feature_count"), int)
                or not 0 <= layer["feature_count"] <= 3):
                continue
            gis_rows.append(
                '<article class="site"><div class="meta"><span>BOUNDED OFFICIAL GIS SAMPLE</span></div>'
                '<h3>' + e(layer.get("label", "Unknown source")) + '</h3>'
                '<p><strong>' + e(layer.get("feature_count", 0)) + '</strong> bounded example polygons observed. '
                'Dataset not exhaustively downloaded. No site intersection, land ownership or planning clearance established.</p>'
                '<div class="evidence"><strong>Source catalogue:</strong> <a target="_blank" rel="noopener noreferrer" href="'
                + e(layer.get("catalogue", "#")) + '">Official publisher ↗</a></div>'
                '<div class="evidence"><strong>Licence:</strong> ' + e(layer.get("licence", "NOT VERIFIED")) + '</div>'
                '<div class="evidence"><strong>Attribution:</strong> ' + e(layer.get("attribution", "")) + '</div>'
                '<div class="risk">' + e(layer.get("warning", "Independent professional review required")) + '</div></article>'
            )
        if gis_rows:
            gis_content = '<div class="cards">' + "".join(gis_rows) + '</div><p class="foot">Official sample receipt: ' + e(gis_snapshot.get("observed_at_utc", "not supplied")) + '. Sample status is not a completed parcel review.</p>'
    return """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>Empire AI | CA18567 Land Intelligence Private Demonstrator</title>
<style>
:root{color-scheme:dark;background:#070e1a;color:#eaf0fb;font-family:system-ui,-apple-system,sans-serif}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(ellipse at 70% -10%,#19365e,transparent 40%),#070e1a}
main{max-width:1170px;padding:48px 24px 80px;margin:auto}
header{border-bottom:1px solid #33445b;padding-bottom:30px;margin-bottom:30px}
.tag{color:#f0c46e;letter-spacing:.18em;text-transform:uppercase;font-size:11px;font-weight:700}
h1{font-size:clamp(30px,5vw,58px);letter-spacing:-.045em;line-height:1.1;margin:14px 0}
h2{font-size:23px;margin:40px 0 16px}h3{font-size:23px;margin:14px 0}
p{line-height:1.65;color:#c0cee0}header p{max-width:820px}
.banner{margin-top:22px;padding:13px 17px;border:1px solid #b88b4a;background:#2a261e;color:#f4d7a0;border-radius:9px}
.stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}
.stat,.site,.panel{background:#101e31;border:1px solid #293b52;border-radius:13px;padding:20px}
.stat strong{font-size:30px;display:block;color:#f6f6f6}.stat small{color:#b1c2d7}
.tools{display:flex;gap:12px;flex-wrap:wrap;margin:20px 0}
input,select{background:#13233a;color:#f2f5f9;border:1px solid #405673;padding:12px;border-radius:8px;font:inherit}
input{flex:1;min-width:220px}.cards{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}
.meta{display:flex;gap:12px;flex-wrap:wrap;color:#9eb8dc;font-size:11px;text-transform:uppercase;letter-spacing:.07em}
.category{color:#e9c98b;background:#352d1e;padding:7px 10px;border-radius:6px;display:inline-block;font-size:12px}
.evidence{color:#bdd1ea;margin:9px 0;line-height:1.5;font-size:13px;overflow-wrap:anywhere}
a{color:#8cbaff}.risk{padding:11px;margin-top:15px;border-left:3px solid #d6a965;background:#192333;font-size:12px;line-height:1.7;color:#ced8e7}
details{margin-top:14px;color:#ccd8e6}summary{cursor:pointer;color:#c3d9f4}li{line-height:1.8;color:#b6c5d9}
.foot{font-size:13px;color:#9eb0c8} .site[hidden]{display:none}
@media(max-width:750px){.cards{grid-template-columns:1fr}.stats{grid-template-columns:repeat(2,1fr)}main{padding:24px 15px}}
</style></head><body><main><header>
<div class="tag">Empire AI / Original EmpireOS / Tender Consultant / Private Research</div>
<h1>Dublin–Belfast<br>Land Intelligence</h1>
<p>A source-linked working method sample for CA18567. Demonstrates evidence classification, cross-border opportunities and due-diligence gaps. It is <strong>not</strong> a bidder qualification, land valuation, RFQ-compliant guide or investment recommendation.</p>
<div class="banner">RESEARCH ONLY · No parcel title verified · No GIS overlays · No investor-ready opportunities · Not approved for publication or tender submission</div>
</header>
<section class="stats">
<div class="stat"><strong>4</strong><small>Public-source examples</small></div>
<div class="stat"><strong>2</strong><small>Jurisdictions</small></div>
<div class="stat"><strong>0</strong><small>Verified investable sites</small></div>
<div class="stat"><strong>0</strong><small>Qualified specialists appointed</small></div>
</section>
<h2>Traceable opportunity research</h2>
<p>The catalogue intentionally distinguishes promoted development land, existing commercial buildings and historical land holdings. Public marketing statements are not treated as verified current stock.</p>
<div class="tools"><input id="search" type="search" placeholder="Filter by site or geography" aria-label="Search opportunity examples">
<select id="jurisdiction" aria-label="Filter jurisdiction"><option value="">All jurisdictions</option><option>Northern Ireland</option><option>Republic of Ireland</option></select>
<select id="kind" aria-label="Filter evidence type"><option value="">All evidence types</option><option value="DEVELOPMENT_LAND">Development land</option><option value="EXISTING_BUILDING">Existing building — exclude</option><option value="HISTORICAL_LANDBANK">Historical landbank</option></select></div>
<div class="cards" id="cards">""" + "".join(rows) + """</div>
<p class="foot" id="count" aria-live="polite">4 examples displayed</p>
<h2>Cross-border evidence plan</h2><section class="panel">
<p><strong>NI:</strong> planning via applicable local plans and planning portal, official environmental/flood, infrastructure, title and asset promoter evidence. <strong>ROI:</strong> MyPlan/local development plans, Tailte Éireann rights-checked mapping, planning, environment, title and IDA/landowner confirmations.</p>
<p><strong>Publication gate:</strong> licence confirmation for every map/dataset, reviewer-signed source register, landowner/promoter authority where required, site-specific planning and title review, and qualified independent professional sign-off.</p>
<ol><li>Retrieve complete issuer RFQ and exact site scope.</li><li>Contract qualified land/planning and GIS specialists under permitted arrangement.</li><li>Screen and verify individually identified parcels; do not infer ownership or current availability.</li><li>Deliver evidence-backed investor narrative with reviewed map rights and dates.</li></ol>
</section>
<h2>Live official geospatial evidence</h2>""" + gis_content + """
<h2>Source and licensing register</h2><section class="panel"><ul>""" + links + """</ul></section>
<p class="foot">Generated locally in EmpireOS from manually reviewed publicly available publisher pages (review date 24 October 2026). No live supplier portal, new scraping, database operations, outbound, public deployment or payment activity. All dimensions and opportunity statements refer to the publisher's claims at review, not independent verification.</p>
</main><script>
(function(){
const sites=Array.from(document.querySelectorAll('.site'));
const q=document.getElementById('search'),j=document.getElementById('jurisdiction'),k=document.getElementById('kind'),count=document.getElementById('count');
function update(){let n=0;for(const el of sites){
const ok=(!q.value||el.textContent.toLowerCase().includes(q.value.toLowerCase()))
&&(!j.value||el.dataset.area===j.value)&&(!k.value||el.dataset.kind===k.value);
el.hidden=!ok;if(ok)n++;}
count.textContent=n+' of '+sites.length+' examples displayed';}
[q,j,k].forEach(el=>el.addEventListener('input',update));
})();
</script></body></html>"""


def write_private_demo(root: Path, now: datetime | None = None) -> dict:
    folder = _private_directory(root)
    report = build_report(now=now)
    _atomic_private(folder / JSON_NAME, json.dumps(report, indent=2, sort_keys=True) + "\n")
    gis = None
    snapshot_file = folder / "ca18567_official_gis_snapshot_latest.json"
    if snapshot_file.exists() and not snapshot_file.is_symlink():
        st = snapshot_file.stat()
        if (stat.S_ISREG(st.st_mode) and st.st_uid == os.geteuid()
            and stat.S_IMODE(st.st_mode) == 0o600 and st.st_size <= 200000):
            try:
                gis = json.loads(snapshot_file.read_text(encoding="utf-8"))
            except (UnicodeError,ValueError):
                gis = None
    _atomic_private(folder / HTML_NAME, render_html(report, gis_snapshot=gis))
    return report
