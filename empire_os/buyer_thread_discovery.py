"""Bounded discovery of additional two-way Gmail buyer threads; OBSERVE only.

Only source-bound, DMARC-aligned, founder-corresponded threads may join an
already known relationship. Unknown domains remain review-only candidates.
Body text is never returned or persisted, only deterministic event codes.
"""
from __future__ import annotations

from datetime import datetime, timezone
from email.utils import getaddresses
import re
from typing import Any, Mapping

from empire_os.buyer_mail_semantics import recognize_message_payload

HEX = re.compile(r"^[0-9a-f]{16,32}$")
DOMAIN = re.compile(r"^[a-z0-9-]+(?:\.[a-z0-9-]+)+$")
SELF = "flavag83@gmail.com"
BLOCKED_DOMAINS = frozenset((
    "gmail.com","yahoo.com","outlook.com","hotmail.com","icloud.com",
    "aol.com","live.com","googlemail.com","proton.me","protonmail.com",
))
MAX_CANDIDATE_PAGES = 2
MAX_CHECKED = 12
PAGE_SIZE = 100


def _addresses(value: object) -> set[str]:
    if not isinstance(value, str) or len(value) > 800 or any(
        c in value for c in ("\r","\n","\x00")
    ):
        return set()
    addresses = {address.lower() for _, address in getaddresses([value])}
    return {a for a in addresses if a.count("@")==1 and
            DOMAIN.fullmatch(a.rsplit("@",1)[-1]) and len(a)<254}


def _headers(msg: Mapping[str, Any]) -> dict[str, str]:
    return {h.get("name","").lower():h.get("value","") for h in
            (msg.get("payload") or {}).get("headers", [])
            if isinstance(h, Mapping) and
            h.get("name","").lower() in ("from","to","authentication-results")}


def _dmarc_aligned(h: Mapping[str,str], domain: str) -> bool:
    results = h.get("authentication-results","").lower().lstrip()
    # Require a Gmail-issued header, not an apparent pass in message content.
    if not results.startswith("mx.google.com;"):
        return False
    # For a new thread require an exact aligned From domain and DMARC pass.
    return bool(re.search(
        r"\bdmarc=pass\b[^;\n]{0,160}\bheader\.from="
        + re.escape(domain) + r"\b", results
    ))


def _anchors(source: Mapping[str, Any]) -> dict[str, tuple[str, str] | None]:
    # Only identities already established by a prior source-bound two-way
    # relationship; research-only prospects and ambiguous domains are not
    # sufficient for automatic relationship linking.
    grouped: dict[str, set[tuple[str,str]]] = {}
    for row in source.get("threads", []):
        if not isinstance(row, Mapping) or not row.get("last_inbound_message_id") or not row.get("last_outbound_message_id"):
            continue
        key = row.get("entity_key")
        company = row.get("company")
        if not isinstance(key,str) or not isinstance(company,str):
            continue
        for domain in row.get("identity_domains", []):
            if isinstance(domain,str) and DOMAIN.fullmatch(domain) and domain not in BLOCKED_DOMAINS:
                grouped.setdefault(domain,set()).add((key,company))
    return {d:(next(iter(values)) if len(values)==1 else None)
            for d,values in grouped.items()}


def _evaluate(thread: Mapping[str, Any], *, source: Mapping[str, Any],
              collected_at: datetime) -> dict[str, Any] | None:
    tid=thread.get("id")
    msgs=thread.get("messages")
    if not isinstance(tid,str) or not HEX.fullmatch(tid):
        return None
    if not isinstance(msgs,list) or not 2 <= len(msgs) <= 80:
        return None
    sent_recipients: set[str] = set()
    incoming: list[tuple[str,Mapping[str, Any],dict[str,str],datetime]]=[]
    outbound: list[tuple[Mapping[str,Any],datetime]]=[]
    for msg in msgs:
        if not isinstance(msg, Mapping) or not HEX.fullmatch(str(msg.get("id",""))):
            return None
        try:
            time=datetime.fromtimestamp(int(msg["internalDate"])/1000, timezone.utc)
        except (ValueError, TypeError, KeyError, OverflowError):
            return None
        if time>collected_at or (collected_at-time).days>40:
            continue
        labels=set(msg.get("labelIds") or [])
        if labels & {"DRAFT","TRASH","SPAM"}:
            continue
        h=_headers(msg)
        senders=_addresses(h.get("from",""))
        if len(senders)!=1:
            continue
        sender=next(iter(senders))
        if "SENT" in labels and sender==SELF:
            sent_recipients.update(_addresses(h.get("to","")))
            outbound.append((msg,time))
        elif "SENT" not in labels and sender!=SELF:
            incoming.append((sender,msg,h,time))
    if not outbound or not incoming:
        return None
    # At least one exact buyer mailbox must appear both as the founder's
    # recipient and as an authenticated return sender in that thread.
    valid=[]
    for sender,msg,h,time in incoming:
        domain=sender.rsplit("@",1)[1]
        if sender not in sent_recipients or domain in BLOCKED_DOMAINS:
            continue
        if not _dmarc_aligned(h,domain):
            continue
        valid.append((domain,msg,time))
    domains={d for d,_,_ in valid}
    if len(domains)!=1:
        return None
    domain=next(iter(domains))
    anchors=_anchors(source)
    pinned=anchors.get(domain)
    # The domain is known from a prior two-way buyer relationship or held
    # for identity review; neither creates execution authority.
    claim_events=[]
    for _,msg,time in valid:
        for code in recognize_message_payload(msg.get("payload") or {}):
            claim_events.append({
                "message_id":msg["id"], "event_code":code,
                "observed_at":time.isoformat(),
                "evidence_grade":"EMAIL_REPORTED_UNVERIFIED","direction":"inbound",
            })
    for msg,time in outbound:
        for code in recognize_message_payload(msg.get("payload") or {},outbound=True):
            claim_events.append({
                "message_id":msg["id"], "event_code":code,
                "observed_at":time.isoformat(),
                "evidence_grade":"EMAIL_REPORTED_UNVERIFIED","direction":"outbound",
            })
    # A conservative last-ID breadcrumb only; never store correspondent
    # addresses, message bodies, phone numbers or raw authentication headers.
    return {
        "thread_id":tid,
        "domain":domain,
        "entity_key":pinned[0] if pinned else None,
        "company":pinned[1] if pinned else None,
        "status":"KNOWN_TWO_WAY_IDENTITY_REPORTED" if pinned else "NEW_DOMAIN_REQUIRES_IDENTITY_REVIEW",
        "founder_sent_id":max(outbound,key=lambda v:v[1])[0]["id"],
        "founder_sent_at":max(outbound,key=lambda v:v[1])[1].isoformat(),
        "buyer_reply_id":max(valid,key=lambda v:v[2])[1]["id"],
        "buyer_reply_at":max(valid,key=lambda v:v[2])[2].isoformat(),
        "recognized_events":sorted(claim_events,key=lambda v:(v["observed_at"],v["message_id"],v["event_code"]))[:120],
        "provider_auth_dmarc_aligned":True,
        "outbound_authorized":False,
        "buyer_approved":False,
        "execution_authority":"NONE",
    }


def discover(service, source: Mapping[str,Any], *, now:datetime|None=None,
             cursor:int=0, max_checked:int=MAX_CHECKED) -> dict[str,Any]:
    now=(now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    existing={r.get("gmail_thread_id") for r in source.get("threads",[])
              if isinstance(r,Mapping)}
    recent=[]
    seen=set()
    next_token=None
    pages=0
    for _ in range(MAX_CANDIDATE_PAGES):
        opts={"userId":"me","q":"in:sent newer_than:21d",
              "maxResults":PAGE_SIZE}
        if next_token:
            opts["pageToken"]=next_token
        result=service.users().messages().list(**opts).execute()
        pages+=1
        for row in result.get("messages",[]):
            tid=row.get("threadId")
            if (isinstance(tid,str) and HEX.fullmatch(tid)
                    and tid not in seen and tid not in existing):
                seen.add(tid)
                recent.append(tid)
        next_token=result.get("nextPageToken")
        if not next_token:
            break
    max_checked=min(MAX_CHECKED,max(1,int(max_checked)))
    cursor=max(0,int(cursor))
    # Previously discovered unanswered commercial relationships receive
    # two of the existing 12 bounded checks, then cycle other recent threads.
    # Completed paid-only/held responses are not pointlessly re-polled.
    priority=[
        row["thread_id"] for row in source.get("buyer_new_thread_review",[])
        if isinstance(row,Mapping)
        and row.get("status")=="REVIEW_IDENTITY_NO_SEND"
        and row.get("thread_id") in recent
    ][:2]
    unvisited=[tid for tid in recent if tid not in priority]
    normal_count=min(max_checked-len(priority),len(unvisited))
    picked=priority+([unvisited[(cursor+i)%len(unvisited)]
                     for i in range(normal_count)] if unvisited else [])
    review=[]
    for tid in picked:
        thread=service.users().threads().get(userId="me",id=tid,format="full").execute()
        result=_evaluate(thread,source=source,collected_at=now)
        if result:
            review.append(result)
    return {
        "schema_version":"empire.buyer_new_thread_discovery.v1",
        "captured_at":now.isoformat(),
        "scope":"RECENT_SENT_TWO_WAY_ONLY",
        "candidate_thread_count":len(recent),
        "checked_thread_count":len(picked),
        "incomplete_scan":bool(next_token) or len(picked)<len(recent),
        "next_cursor":(cursor+normal_count)%len(unvisited) if unvisited else 0,
        "known_buyer_threads":sum(bool(x["entity_key"]) for x in review),
        "unlinked_review_count":sum(x["entity_key"] is None for x in review),
        "candidates":review,
        "outbound_authorized":False,
        "execution_authority":"NONE",
    }
