"""Read-only reply@mail.empire-ai.co.uk inbox STOP watch for original Permit.

Reuses the original authenticated Workspace Google mailbox service and the
existing explicit-opt-out evidence classifier. No Gmail send/modify, no
EmpireDB writes, no raw sender/body/message IDs persisted in reporting.
A missing alias message or a STOP preview does not prove canonical reply
lineage or committed suppression.
"""
from __future__ import annotations

import base64
from datetime import datetime,timezone,timedelta
from email.utils import getaddresses
from typing import Any,Callable

from empire_os.reply_opt_out_evidence import explicit_opt_out_from_preview

REPLY_ALIAS="reply@mail.empire-ai.co.uk"
QUERY="to:reply@mail.empire-ai.co.uk newer_than:30d"
LIMIT=20
OWN_MAILBOXES={"phil@empire-ai.co.uk","phil@mail.empire-ai.co.uk",REPLY_ALIAS}


def _headers(payload:dict)->dict[str,str]:
    values={}
    rows=payload.get("headers")
    if not isinstance(rows,list) or len(rows)>100:
        raise ValueError("WORKSPACE_ALIAS_HEADERS_UNTRUSTED")
    for item in rows:
        if not isinstance(item,dict):
            raise ValueError("WORKSPACE_ALIAS_HEADERS_UNTRUSTED")
        key=str(item.get("name") or "").casefold()
        if key in ("from","to","subject","reply-to","message-id",
                   "in-reply-to","references"):
            if key in values:
                raise ValueError("WORKSPACE_ALIAS_DUPLICATE_SECURITY_HEADER")
            val=item.get("value")
            if not isinstance(val,str) or len(val)>1500:
                raise ValueError("WORKSPACE_ALIAS_HEADER_UNTRUSTED")
            values[key]=val
    return values


def _text(payload:dict,depth:int=0)->str:
    if depth>4 or not isinstance(payload,dict):
        raise ValueError("WORKSPACE_ALIAS_BODY_UNTRUSTED")
    if payload.get("filename") or payload.get("body",{}).get("attachmentId"):
        return ""
    parts=payload.get("parts") or []
    if parts:
        if not isinstance(parts,list) or len(parts)>12:
            raise ValueError("WORKSPACE_ALIAS_BODY_UNBOUNDED")
        return "\n".join(filter(None,(_text(p,depth+1) for p in parts)))[:600]
    if payload.get("mimeType")!="text/plain":
        return ""
    data=payload.get("body",{}).get("data")
    if not isinstance(data,str) or len(data)>16000:
        return ""
    try:
        return base64.urlsafe_b64decode(
            data+"="*(-len(data)%4)).decode("utf-8")[:600]
    except (ValueError,UnicodeError):
        return ""


def _single_address(value:str)->str:
    parsed=getaddresses([value])
    if len(parsed)!=1:
        return ""
    address=parsed[0][1].casefold()
    return address if (address.count("@")==1 and
                       " " not in address and len(address)<=254) else ""


def inspect(*,service_factory:Callable[[],Any]|None=None,
            now:datetime|None=None)->dict:
    """Bounded live inbox observation. Never infer an eligible sender or write."""
    when=now or datetime.now(timezone.utc)
    result={
        "status":"HELD_WORKSPACE_REPLY_ALIAS_EVIDENCE_UNAVAILABLE",
        "query_scope":"ORIGINAL_WORKSPACE_REPLY_ALIAS_LAST_30_DAYS",
        "workspace_reply_alias_inbox_messages_observed":0,
        "workspace_reply_alias_explicit_stop_candidates":0,
        "workspace_reply_alias_scan_complete":False,
        "workspace_reply_alias_delivery_observed":False,
        "canonical_sent_intent_lineage_verified":False,
        "stop_to_empiredb_suppression_e2e_verified":False,
        "sender_addresses_retained":False,
        "raw_email_bodies_retained":False,
        "database_writes":False,
        "gmail_writes":False,
        "outbound_sent":False,
    }
    try:
        if when.utcoffset() is None:
            raise ValueError("WORKSPACE_ALIAS_OBSERVATION_CLOCK_REQUIRED")
        if service_factory is None:
            from empire_os.google_workspace_mailbox import GoogleWorkspaceMailboxProvider
            service_factory=GoogleWorkspaceMailboxProvider()._service
        api=service_factory()
        page=api.users().messages().list(
            userId="me",q=QUERY,maxResults=LIMIT,
            fields="messages(id),nextPageToken",
        ).execute()
        ids=[r.get("id") for r in page.get("messages") or []]
        if (not isinstance(ids,list) or len(ids)>LIMIT
            or any(not isinstance(x,str) or not 8<=len(x)<=48 or
                   not x.isalnum() for x in ids)
            or len(ids)!=len(set(ids))):
            raise ValueError("WORKSPACE_ALIAS_UNTRUSTED_LIST")
        complete=not bool(page.get("nextPageToken"))
        inbox=0;stops=0
        for ident in ids:
            item=api.users().messages().get(
                userId="me",id=ident,format="full").execute()
            if item.get("id")!=ident or not isinstance(item.get("payload"),dict):
                raise ValueError("WORKSPACE_ALIAS_UNTRUSTED_MESSAGE")
            labels=set(item.get("labelIds") or [])
            if ("INBOX" not in labels or
                labels.intersection({"SENT","DRAFT","TRASH","SPAM"})):
                continue
            h=_headers(item["payload"])
            if _single_address(h.get("to",""))!=REPLY_ALIAS:
                continue
            sender=_single_address(h.get("from",""))
            if not sender or sender in OWN_MAILBOXES:
                continue
            stamp=item.get("internalDate")
            if not isinstance(stamp,str) or not stamp.isdigit():
                raise ValueError("WORKSPACE_ALIAS_DATE_UNVERIFIED")
            received=datetime.fromtimestamp(int(stamp)/1000,timezone.utc)
            if received>when.astimezone(timezone.utc)+timedelta(minutes=2):
                raise ValueError("WORKSPACE_ALIAS_FUTURE_MESSAGE")
            inbox+=1
            visible=_text(item["payload"])
            proof=explicit_opt_out_from_preview(h.get("subject",""),visible)
            if proof["explicit_opt_out_observed"]:
                stops+=1
        return {**result,
            "status":("REPLY_ALIAS_EXPLICIT_STOP_EVIDENCE_HELD_FOR_CANONICAL_LINK"
                      if stops else "REPLY_ALIAS_INBOX_OBSERVED_NO_STOP"
                      if inbox else "REPLY_ALIAS_NO_OBSERVED_INBOUND_MESSAGES"),
            "workspace_reply_alias_inbox_messages_observed":inbox,
            "workspace_reply_alias_explicit_stop_candidates":stops,
            "workspace_reply_alias_scan_complete":complete,
            "workspace_reply_alias_delivery_observed":inbox>0,
        }
    except Exception:
        return result
