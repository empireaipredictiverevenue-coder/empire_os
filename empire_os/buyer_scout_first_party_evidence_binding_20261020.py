"""Cross-check each A2A owner website packet with actual collector readback.

Readback and owner packets are both untrusted until individual URL, market,
sector, fetch state, original HTML SHA and parser digest agree. Never upgrade
self-description to independently validated buyer evidence.
"""
from __future__ import annotations
from collections.abc import Mapping
from typing import Any

SCHEMA="empire.a2a.first_party_source_recovery_review.v1"

def verify_site_source_binding(
    packets: list[Mapping[str,Any]],
    readback: Mapping[str,Any] | None,
)-> dict[str,bool]:
    if readback is None:
        return {str(p.get("public_company_website")):False for p in packets}
    records=readback.get("source_records")
    if (not isinstance(records,list) or len(records)!=len(packets)
            or readback.get("sites_read")!=len(records)):
        raise ValueError("SOURCE_BINDING_RECORD_SET_INCOMPLETE")
    seen:dict[str,Mapping[str,Any]]={}
    for row in records:
        if not isinstance(row,Mapping):
            raise ValueError("SOURCE_BINDING_ROW_INVALID")
        url=row.get("source_url")
        if not isinstance(url,str) or url in seen:
            raise ValueError("SOURCE_BINDING_DUPLICATE_URL")
        if (row.get("buyer_or_lead_verified") is not False
                or row.get("contact_allowed") is not False):
            raise ValueError("SOURCE_BINDING_BUYER_ESCALATION")
        seen[url]=row
    bound:dict[str,bool]={}
    for packet in packets:
        url=packet.get("public_company_website")
        if url not in seen or url in bound:
            raise ValueError("SOURCE_BINDING_OWNER_PACKET_MISMATCH")
        row=seen[url]
        good=row.get("read_status")=="HTTP_200"
        if (row.get("read_status")!=packet.get("source_read_status")
                or row.get("sector")!=packet.get("target_sector")
                or row.get("market")!=packet.get("target_market")
                or row.get("source_sha256_if_http_200")!=packet.get("observed_source_sha256")):
            raise ValueError("SOURCE_BINDING_SHA_OR_SCOPE_MISMATCH")
        if good:
            if (row.get("scrapling_document_matches_collector_sha") is not True
                    or row.get("crawl4ai_digest_matches_collector") is not True
                    or packet.get("scrapling_structured_page_parsed") is not True
                    or row.get("scrapling_structured_page_parsed") is not True
                    or row.get("crawl4ai_offline_markdown_extracted") is not True):
                raise ValueError("SOURCE_BINDING_PARSER_PROOF_MISSING")
        elif row.get("source_sha256_if_http_200") is not None:
            raise ValueError("SOURCE_BINDING_HELD_SITE_HAS_HTML_SHA")
        bound[url]=good
    return bound
