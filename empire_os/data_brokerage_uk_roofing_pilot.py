"""Bounded, dated UK roofing evidence sample in ORIGINAL Empire Data Brokerage.

Source PlanIndex CC BY 4.0, council-derived open CSV; council independent
register check for each shortlisted or excluded record. No contact enrichment,
private email/address exports, CRM writes, sales claims or outbound.
"""
from __future__ import annotations
from collections import Counter
from datetime import datetime,date,timezone,timedelta
from hashlib import sha256
from io import StringIO
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
import csv,json,os,re,stat,tempfile,requests
from bs4 import BeautifulSoup

SCHEMA="empire.data_brokerage.uk_construction_roofing_evidence.v1"
SOURCE_REPO_SHA="3c060f812e20edcf27214b2d6c7bb8d94efc7b18"
SOURCE="https://raw.githubusercontent.com/PlanIndex/uk-planning-applications/"+SOURCE_REPO_SHA+"/councils/southampton.csv"
PLANINDEX_BASE="https://planindex.co.uk/planning-applications/southampton/"
COUNCIL_HOST="planningpublicaccess.southampton.gov.uk"
COMPANY_SOURCE="https://www.constructionsales.co.uk/about/"
SOURCE_LICENCE="CC BY 4.0"
SOURCE_CREDIT="PlanIndex, planindex.co.uk"
MAX_CSV=175_000
MAX_HTML=180_000
DEST=Path("/srv/empire_os/runtime/data_brokerage")
RECEIPT=DEST/"uk_southampton_roof_project_evidence_latest.json"
MARKDOWN=DEST/"uk_southampton_roof_project_evidence_latest.md"
CSV=DEST/"uk_southampton_roof_project_evidence_latest.csv"
VALID_STATUSES={"Awaiting decision"}
REFERENCE=re.compile(r"26/\d{4,6}/[A-Z]{2,6}\Z")
POSTCODE=re.compile(r"SO(?:1[0-9])\Z")
DATE=re.compile(r"20\d{2}-\d{2}-\d{2}\Z")
URL_SLUG=re.compile(r"26-\d{4,6}-[a-z]{2,6}\Z")
KEY=re.compile(r"[A-Z0-9]{10,20}\Z")
MIN_VALID=date(2026,10,1)
CONTRACT="founder_original_intelligence_reports"
PILOT_LANE="SOUTHAMPTON_ROOF_DORMER_EVIDENCE"
CORE=re.compile(r"\b(?:roof alterations?|roof change|roof extension|roof conversion|roof replacement|replacement roof|raise(?:d|ing)? the roof|roof.*dormer|dormer.*roof|dormer windows|loft conversion)\b",re.I)
SOLAR=re.compile(r"\b(?:solar photovoltaic|solar panels?|photovoltaic panels)\b",re.I)
ADJACENT=re.compile(r"\b(?:rooflights?|roof lights?|dormer)\b",re.I)
NEGATIVE=re.compile(r"\b(?:storage for roofing materials|roofing materials and staff parking|archaeological watching brief)\b",re.I)
NONSTART={"MMA","NMA","DIS","DIC","TPO","LIS","PLDC"}
FIELDS=("reference","postcode_district","category","status","validated_date","planindex_url","proposal")
class Hold(ValueError):pass
def need(ok,code):
 if not ok:raise Hold(code)
def get(url,max_bytes=MAX_HTML,session=None):
 p=urlsplit(url)
 need(p.scheme=="https" and p.hostname in {
  "raw.githubusercontent.com","planindex.co.uk",COUNCIL_HOST}, "UNAPPROVED_SOURCE_URL")
 sess=session or requests.Session()
 res=sess.get(url,timeout=(4,14),allow_redirects=False,
   headers={"Accept":"text/html,text/csv,*/*;q=0.3","User-Agent":"EmpireAI-OriginalBrokerageEvidence/1.0 (source-linked research)"},stream=True)
 need(res.status_code==200,"SOURCE_HTTP_NOT_200")
 chunks=[];total=0
 for blob in res.iter_content(chunk_size=8192):
  total+=len(blob)
  need(total<=max_bytes,"SOURCE_BYTES_EXCEEDED")
  chunks.append(blob)
 need(total>0,"SOURCE_EMPTY")
 return b"".join(chunks)
def source_rows(payload:bytes,now:datetime):
 need(100<len(payload)<=MAX_CSV,"COUNCIL_CSV_BOUNDS_INVALID")
 try:source=payload.decode("utf-8-sig")
 except UnicodeDecodeError as exc:raise Hold("COUNCIL_SOURCE_NOT_UTF8") from exc
 reader=csv.DictReader(StringIO(source))
 need(set(FIELDS).issubset(set(reader.fieldnames or [])),"COUNCIL_SOURCE_COLUMNS_CHANGED")
 rows=list(reader)
 need(10<len(rows)<=1500,"COUNCIL_SOURCE_ROWS_OUTSIDE_LIMITS")
 have=set();out=[]
 for row in rows:
  ref=row.get("reference","")
  if not REFERENCE.fullmatch(ref) or ref in have:continue
  have.add(ref)
  code=row["validated_date"]
  if not DATE.fullmatch(code):continue
  try:validated=date.fromisoformat(code)
  except ValueError:continue
  if not MIN_VALID<=validated<=now.date():continue
  if row["status"] not in VALID_STATUSES:continue
  proposal=row["proposal"]
  if not isinstance(proposal,str) or len(proposal)>1000:continue
  if not (CORE.search(proposal) or ADJACENT.search(proposal)
          or SOLAR.search(proposal) or NEGATIVE.search(proposal)):continue
  postcode=row.get("postcode_district","")
  if not POSTCODE.fullmatch(postcode):continue
  url=row.get("planindex_url","")
  p=urlsplit(url)
  if (p.scheme!="https" or p.hostname!="planindex.co.uk"
      or p.path!=("/planning-applications/southampton/"+ref.lower().replace("/","-"))
      or p.query or p.fragment):continue
  typ=ref.rsplit("/",1)[-1]
  if NEGATIVE.search(proposal):
   rank=0;category="EXCLUDED_NOT_ROOF_WORK";reason="Background planning conditions or roofing-material storage, not a new roofing project."
  elif typ in NONSTART:
   rank=0;category="EXCLUDED_FOLLOW_ON_OR_ADMINISTRATIVE";reason="Condition discharge, amendment or lawful-development certificate; not a confirmed new roofing work order."
  elif CORE.search(proposal):
   rank=5;category="RESEARCH_PRIORITY_ROOF_LOFT";reason="Explicit roof configuration/dormer/loft works in council proposal."
  elif SOLAR.search(proposal):
   rank=3;category="ADJACENT_ROOFTOP_SOLAR";reason="Roof-based solar proposal, not a confirmed roofing contractor requirement."
  elif ADJACENT.search(proposal):
   rank=2;category="ADJACENT_ROOFLIGHT_EXTENSION";reason="Rooflight or small roof interface; not proof of roofing contract."
  else:continue
  out.append({
   "reference":ref,"council":"Southampton City Council",
   "postcode_district":postcode,"validated_date":code,
   "status_feed":row["status"],"category_feed":row["category"],
   "proposal_summary":proposal[:260],
   "planindex_url":url,"research_tier":category,
   "research_rank":rank,"research_reason":reason,
   "proposal_is_job_order":False,
   "planning_permission_or_work_award_confirmed":False,
   "personal_contact_disclosed":False,
  })
 return out,len(rows)
def pick(rows):
 positives=sorted((r for r in rows if r["research_rank"]>0),
    key=lambda r:(-r["research_rank"],-int(r["validated_date"].replace("-","")),r["reference"]))
 negatives=sorted((r for r in rows if r["research_rank"]==0),
    key=lambda r:(0 if "roofing materials" in r["proposal_summary"].lower()
                   else 1 if r["reference"].endswith("/PLDC")
                   else 2,
                   -int(r["validated_date"].replace("-","")),r["reference"]))
 need(len(positives)>=5 and len(negatives)>=1,"INSUFFICIENT_QUALITY_OR_NEGATIVE_CASES")
 # Maximum ten: eight project research signals and two genuine exclusions.
 return positives[:8]+negatives[:2]
def council_record(row,fetch=get):
 home=fetch(row["planindex_url"])
 soup=BeautifulSoup(home,"html.parser")
 links=[a.get("href") for a in soup.select("a[href]") if COUNCIL_HOST in str(a.get("href"))]
 valid=[]
 for link in links:
  parts=urlsplit(link)
  q=parse_qs(parts.query)
  if (parts.scheme=="https" and parts.hostname==COUNCIL_HOST and
      parts.path=="/online-applications/applicationDetails.do" and
      len(q.get("keyVal",[]))==1 and KEY.fullmatch(q["keyVal"][0])):
   valid.append("https://"+COUNCIL_HOST+
      "/online-applications/applicationDetails.do?activeTab=summary&keyVal="+q["keyVal"][0])
 need(bool(valid),"OFFICIAL_REGISTER_LINK_MISSING")
 official=sorted(set(valid))[0]
 html=fetch(official)
 record=BeautifulSoup(html,"html.parser")
 fields={}
 for tr in record.select("tr"):
  values=[c.get_text(" ",strip=True) for c in tr.find_all(["th","td"])]
  if len(values)>=2:fields[values[0]]=values[1]
 need(fields.get("Reference")==row["reference"],"COUNCIL_REFERENCE_MISMATCH")
 need(fields.get("Status")==row["status_feed"],"COUNCIL_STATUS_CHANGED")
 actual_date=fields.get("Application Validated")
 need(bool(actual_date) and datetime.strptime(actual_date,"%a %d %b %Y").date().isoformat()
      ==row["validated_date"],"COUNCIL_DATE_MISMATCH")
 proposal=fields.get("Proposal","")
 norm=lambda s:re.sub(r"\W+"," ",s).casefold().strip()
 # We only require the leading 70 characters to match, since the CSV
 # abbreviates long source text and owner systems may normalise whitespace.
 expected=norm(row["proposal_summary"])[:65]
 need(expected and norm(proposal).startswith(expected[:35]),
      "COUNCIL_PROPOSAL_MISMATCH")
 row=dict(row)
 row["official_council_url"]=official
 row["official_council_verified"]=True
 row["official_council_status_as_of"]="Awaiting decision"
 row["independent_official_reference_matched"]=True
 row["official_council_html_sha256"]=sha256(html).hexdigest()
 row["planindex_application_page_sha256"]=sha256(home).hexdigest()
 return row
def build(*,now=None,fetch=get,source_commit=SOURCE_REPO_SHA):
 now=(now or datetime.now(timezone.utc)).astimezone(timezone.utc)
 need(isinstance(source_commit,str) and re.fullmatch(r"[a-f0-9]{40}",source_commit) is not None,"INVALID_DAILY_SOURCE_COMMIT")
 source_url=SOURCE.replace(SOURCE_REPO_SHA,source_commit)
 payload=fetch(source_url)
 candidates,csv_rows=source_rows(payload,now)
 picked=pick(candidates)
 checks=[];fails=[]
 for row in picked:
  try:checks.append(council_record(row,fetch=fetch))
  except (Hold,requests.RequestException,ValueError,TypeError) as exc:
   fails.append({"reference":row["reference"],"code":type(exc).__name__,
                 "excluded_from_verified_sample":True})
 # Never promote candidates without direct official register verification.
 need(len(checks)>=5,"OFFICIAL_REGISTER_VERIFICATION_INSUFFICIENT")
 need(sum(r["research_rank"]>0 for r in checks)>=5,"NOT_ENOUGH_VERIFIED_ROOF_SIGNALS")
 summary={
  "raw_csv_rows":csv_rows,
  "recent_awaiting_trade_keyword_candidates":len(candidates),
  "sampled_candidates":len(picked),
  "official_verified_cases":len(checks),
  "research_priorities":sum(x["research_tier"]=="RESEARCH_PRIORITY_ROOF_LOFT" for x in checks),
  "roof_solar_adjacent":sum(x["research_tier"].startswith("ADJACENT") for x in checks),
  "deliberate_false_positives_excluded":sum(x["research_rank"]==0 for x in checks),
  "official_verification_holds":len(fails),
 }
 report={
  "schema_version":SCHEMA,"status":"OFFICIAL_CROSS_CHECKED_ORIGINAL_UK_CONSTRUCTION_PILOT",
  "as_of_utc":now.isoformat(),"source_data_as_of":now.date().isoformat(),
  "market":"GB","region":"Southampton","sector":"roof/loft/rooftop work",
  "existing_original_brokerage_product":CONTRACT,
  "original_agency_pilot_problem":"Does source-supported project prequalification help prioritise calls beyond generic project leads?",
  "source":{"publisher":"PlanIndex open planning applications","source_url":source_url,
   "source_repository_commit":source_commit,"source_csv_sha256":sha256(payload).hexdigest(),
   "source_licence":SOURCE_LICENCE,"required_credit":SOURCE_CREDIT,
   "licence_url":"https://creativecommons.org/licenses/by/4.0/",
   "source_terms_url":"https://planindex.co.uk/open-data",
   "original_authority":"Southampton City Council planning register",
   "independent_council_checks":"verified reference, status, validation date and proposal"},
  "summary":summary,"research_records":checks,
  "unverified_source_holds":fails,
  "no_personal_address_export":True,"contractor_or_property_owner_contact_verified":False,
  "no_explicit_customer_buyer_intent":True,"no_signed_contract":True,
  "status_not_guaranteed_to_remain_current":True,
  "planning_application_not_a_work_order":True,"no_outreach":True,
  "no_crm_writes":True,"no_payment":True,
  "customer_delivery":False,
 }
 return report
def preview(report):
 summary=report["summary"]
 lines=["# Empire AI | Southampton roofing and loft project evidence",
  "", "**Original Data Brokerage pilot · source-checked · unsent**",
  "", "Agency use case: show a construction sales team which publicly submitted "
      "roof/loft/solar proposals deserve further research, and which keyword hits do not.",
  "", "## Evidence window", "",
  "Southampton City Council planning register, via PlanIndex daily open-data file.",
  "Feed attribution: PlanIndex (planindex.co.uk), CC BY 4.0.",
  "Original council pages were independently checked for application reference, proposal, validation date and current status.",
  "As of "+report["as_of_utc"][:16]+" UTC. Applications are not buyer enquiries or job orders.",
  "",
  "## Verified project research records", ""]
 for r in report["research_records"]:
  lines.extend([
   "### "+r["reference"]+" — "+r["research_tier"],
   "Location district: "+r["postcode_district"]+
      " · validated: "+r["validated_date"]+" · council status: "+r["official_council_status_as_of"],
   "Published proposal: "+r["proposal_summary"],
   "Qualification: "+r["research_reason"],
   "Council: "+r["official_council_url"],
   "PlanIndex: "+r["planindex_url"],""])
 lines+=["## Qualification outcome", "",
  "Raw council feed rows: "+str(summary["raw_csv_rows"]),
  "Recent pending trade-language candidates: "+str(summary["recent_awaiting_trade_keyword_candidates"]),
  "Independent council cross-checks passed: "+str(summary["official_verified_cases"]),
  "Core roof/loft priority cases: "+str(summary["research_priorities"]),
  "Adjacent roof/solar cases: "+str(summary["roof_solar_adjacent"]),
  "Excluded keyword false positives: "+str(summary["deliberate_false_positives_excluded"]),
  "Independently held/unverified: "+str(summary["official_verification_holds"]),
  "", "## What to test with Contractors Marketing Services", "",
  "Compare a five to ten case project-prequalification sheet with the same "
  "niche/area in their Planning Pipe / Prospector workflow. Measure whether "
  "dated council references, decisions, amendments and false positives save "
  "manual research before a sales call.",
  "This preview does not prove incremental records against that provider. "
  "It is not a customer lead list, it contains no residential street address "
  "or person details, and it does not authorise contact with applicants.",
  "",
  "## Attribution and usage", "",
  "PlanIndex, planindex.co.uk (CC BY 4.0): "+report["source"]["source_terms_url"],
  "Original register: Southampton City Council. Data is subject to corrections "
  "and change. This internal research snapshot has not been sent, sold or published.",
  ""]
 return "\n".join(lines)
def csv_payload(report):
 from io import StringIO
 buff=StringIO()
 writer=csv.DictWriter(buff,fieldnames=[
  "reference","postcode_district","validated_date","official_council_status_as_of",
  "research_tier","research_rank","proposal_summary","research_reason",
  "official_council_url","planindex_url","official_council_verified",
  "planning_permission_or_work_award_confirmed"],extrasaction="ignore")
 writer.writeheader()
 for row in report["research_records"]:writer.writerow(row)
 return buff.getvalue().encode()
def _atomic(path,blob):
 need(path.parent.is_dir() and not path.parent.is_symlink()
   and path.parent.stat().st_uid==os.geteuid()
   and stat.S_IMODE(path.parent.stat().st_mode)==0o700
   and not path.is_symlink(),"BROKERAGE_PRIVATE_SOURCE_DIRECTORY_REQUIRED")
 fd,temp=tempfile.mkstemp(prefix=".southampton-verified-",dir=path.parent)
 try:
  with os.fdopen(fd,"wb") as f:
   os.fchmod(f.fileno(),0o600);f.write(blob);f.flush();os.fsync(f.fileno())
  os.replace(temp,path)
 finally:
  if os.path.exists(temp):os.unlink(temp)
def run(*,now=None,fetch=get,source_commit=SOURCE_REPO_SHA):
 j=build(now=now,fetch=fetch,source_commit=source_commit)
 _atomic(RECEIPT,(json.dumps(j,sort_keys=True,indent=2)+"\n").encode())
 _atomic(MARKDOWN,preview(j).encode())
 _atomic(CSV,csv_payload(j))
 return {"status":j["status"],**j["summary"],
  "source_sha256":j["source"]["source_csv_sha256"],
  "outbound_sent":False,"crm_writes":False,"new_timer":False}
