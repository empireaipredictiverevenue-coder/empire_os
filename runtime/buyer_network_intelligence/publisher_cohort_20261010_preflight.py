#!/usr/bin/env python3
"""One-off read-only exact-contact and domain history review for saved draft cohort.
This file performs no sends, writes, API calls, enrolments or approval changes.
"""
import json
from pathlib import Path
import sys
import os
import re

ROOT=Path("/srv/empire_os")
sys.path.insert(0,str(ROOT))
from scripts.materialize_company_routed_buyer_review import (
    _canonical_contact_history,
    _canonical_exact_outbound_intents,
)

EMAILS = (
    "contact@roofpitch.net",
    "hello@roofingcalculatorusa.com",
    "support@solarbriton.co.uk",
    "contact@getbuilding.co.uk",
    "partners@homecurrent.co.uk",
    "anuj@legaldesire.com",
    "gettradesmen@gmail.com",
    "partners@pavementcalculator.com",
)

def main():
    result={"schema":"empire.publisher_cohort.readonly_history_preflight.v1",
       "mode":"OBSERVE", "cohort_count":len(EMAILS), "database_write":False,
       "outbound_sent":False, "outbound_authorized":False,
       "individual_recipient_suppression_cleared":False,
       "execution_authority":"none"}
    try:
        # The Gmail direct-send exception produced an actual 550 hard bounce.
        # Preserve that hold even before its canonical suppression migration.
        sent = json.loads((ROOT / "docs/commercial/PUBLISHER_RECRUITMENT_GMAIL_SEND_EVIDENCE_20261010.json").read_text())
        if (sent.get("schema_version") != "empire.publisher_recruitment.gmail_sent_evidence.v1"
                or sent.get("source_mailbox") != "flavag83@gmail.com"):
            raise ValueError("UNTRUSTED_GMAIL_DELIVERY_EVIDENCE")
        messages = sent.get("messages")
        if not isinstance(messages, list) or len(messages) > len(EMAILS):
            raise ValueError("INVALID_GMAIL_SEND_HISTORY")
        gmail_sent, hard_bounces, seen_ids = set(), set(), set()
        for message in messages:
            if not isinstance(message, dict):
                raise ValueError("INVALID_GMAIL_SEND_HISTORY")
            recipient = message.get("recipient")
            message_id = message.get("gmail_message_id")
            if (recipient not in EMAILS or recipient in gmail_sent
                    or not isinstance(message_id, str) or len(message_id) < 16
                    or message_id in seen_ids or message.get("gmail_label") != "SENT"):
                raise ValueError("INVALID_OR_DUPLICATE_GMAIL_SEND")
            gmail_sent.add(recipient)
            seen_ids.add(message_id)
            if message.get("recipient_delivery_status") == "BOUNCED_NO_SUCH_USER_550_5_1_1":
                if (message.get("retry_authorized") is not False
                        or not message.get("bounce_gmail_message_id")):
                    raise ValueError("INVALID_HARD_BOUNCE_PROVENANCE")
                hard_bounces.add(recipient)
            elif message.get("recipient_delivery_status") is not None:
                raise ValueError("UNVERIFIED_DELIVERY_EVENT")
        if (sent.get("submitted_to_gmail_count") != len(gmail_sent)
                or sent.get("confirmed_hard_bounce_count") != len(hard_bounces)):
            raise ValueError("GMAIL_HISTORY_TOTALS_CONFLICT")
        if not os.environ.get("EMPIREDB_DSN"):
            raise ValueError("CANONICAL_DSN_UNAVAILABLE")
        _, prior_domains, suppressions = _canonical_contact_history()
        exact_intents = _canonical_exact_outbound_intents(set(EMAILS))
        rows=[]
        for email in EMAILS:
            domain=email.rsplit("@",1)[-1]
            row={"email":email,
                 "exact_suppression_match": email in suppressions,
                 "exact_prior_intent_match":email in exact_intents,
                 "prior_domain_outreach_observed":domain in prior_domains,
                 "other_suppression_on_domain_observed":any(x.endswith("@"+domain) for x in suppressions),
                 "gmail_prior_send_observed":email in gmail_sent,
                 "gmail_hard_bounce_hold":email in hard_bounces,
                 "contact_already_attempted":email in gmail_sent or email in exact_intents,
                 "canonical_checks_completed":True,
                 "send_authorized":False}
            rows.append(row)
        result["rows"]=rows
        result["canonical_read_completed"]=True
        result["exact_suppression_matches"]=sum(x["exact_suppression_match"] for x in rows)
        result["exact_prior_intent_matches"]=sum(x["exact_prior_intent_match"] for x in rows)
        result["domain_history_holds"]=sum(x["prior_domain_outreach_observed"] for x in rows)
        result["gmail_prior_send_count"]=sum(x["gmail_prior_send_observed"] for x in rows)
        result["contact_already_attempted_count"]=sum(x["contact_already_attempted"] for x in rows)
        result["gmail_hard_bounce_holds"]=sum(x["gmail_hard_bounce_hold"] for x in rows)
        result["state"]="REVIEW_ONLY_NO_SEND_AUTHORITY"
    except Exception as exc:
        result["canonical_read_completed"]=False
        result["state"]="HOLD_CANONICAL_HISTORY_UNAVAILABLE"
        result["reason"]=type(exc).__name__
    print(json.dumps(result,sort_keys=True))
    return 0 if result.get("canonical_read_completed") else 2

if __name__=="__main__":
    raise SystemExit(main())
