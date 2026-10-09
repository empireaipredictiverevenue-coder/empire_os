"""Documenso V2 offline multipart contract and independent readback parser.

No network, signatures, contract acceptance, disk writes or envelope creation.
"""
from __future__ import annotations
from collections.abc import Mapping
from hashlib import sha256
import re
from .policy import prepare_agreement
from .lifecycle import ENVELOPE, timestamp

SCHEMA = "empire.documenso.offline_envelope_contract.v1"
EMAIL = re.compile(r"^[^\s@]{1,64}@[^\s@]{1,253}$")


def _field(field: Mapping) -> dict:
    if not isinstance(field, Mapping) or field.get("type") != "SIGNATURE":
        raise ValueError("SIGNATURE_FIELD_REQUIRED")
    page = field.get("page")
    if type(page) is not int or not 1 <= page <= 100:
        raise ValueError("SIGNATURE_PAGE_INVALID")
    coords = [field.get(k) for k in ("positionX", "positionY", "width", "height")]
    if any(type(v) not in (int,float) or v < 0 or v > 100 for v in coords):
        raise ValueError("SIGNATURE_COORDINATES_INVALID")
    x,y,w,h = coords
    if w <= 0 or h <= 0 or x+w > 100 or y+h > 100:
        raise ValueError("SIGNATURE_OUTSIDE_PAGE")
    return {
        "identifier": 0, "type": "SIGNATURE", "page": page,
        "positionX": x, "positionY": y, "width": w, "height": h,
    }


def preview_create(agreement: Mapping, pdf: bytes, signers: list[Mapping]) -> dict:
    """Create only a Documenso multipart request *description*.

    A full PDF parser/layout reviewer is a separate required activation gate.
    """
    proposed = prepare_agreement(agreement)
    if proposed["state"] != "READY_FOR_FOUNDER_SIGNING_RELEASE_REVIEW":
        raise ValueError("AGREEMENT_PREFLIGHT_BLOCKED")
    if not isinstance(pdf, bytes) or not 128 <= len(pdf) <= 16 * 1024 * 1024:
        raise ValueError("PDF_MISSING_OR_OVERSIZED")
    if not pdf.startswith(b"%PDF-") or not pdf.rstrip().endswith(b"%%EOF"):
        raise ValueError("INVALID_PDF_BOUNDARY")
    if sha256(pdf).hexdigest() != proposed["approved_pdf_sha256"]:
        raise ValueError("APPROVED_PDF_HASH_MISMATCH")
    title = agreement.get("document_title")
    if not isinstance(title, str) or not 1 <= len(title.strip()) <= 160:
        raise ValueError("DOCUMENT_TITLE_REQUIRED")
    if not isinstance(signers, list) or len(signers) != 2:
        raise ValueError("EXACTLY_TWO_SIGNERS_REQUIRED")
    expected = {p["role"]: p["entity_id"] for p in agreement["signers"]}
    seen = set()
    recipients = []
    for row in signers:
        if not isinstance(row, Mapping):
            raise ValueError("SIGNER_INPUT_INVALID")
        role, entity = row.get("role"), row.get("entity_id")
        if role not in expected or role in seen or expected[role] != entity:
            raise ValueError("SIGNER_IDENTITY_BINDING_MISMATCH")
        seen.add(role)
        name, email = row.get("name"), row.get("email")
        if (not isinstance(name, str) or not name.strip() or len(name) > 160
            or not isinstance(email, str) or not EMAIL.fullmatch(email)):
            raise ValueError("SIGNER_CONTACT_INVALID")
        fields = row.get("fields")
        if not isinstance(fields, list) or len(fields) != 1:
            raise ValueError("ONE_SIGNATURE_FIELD_PER_SIGNER_REQUIRED")
        recipients.append({
            "email": email.strip().lower(), "name": name.strip(),
            "role": "SIGNER", "fields": [_field(fields[0])],
        })
    if seen != {"FOUNDER", "COUNTERPARTY"} or recipients[0]["email"] == recipients[1]["email"]:
        raise ValueError("BOTH_DISTINCT_SIGNERS_REQUIRED")
    binding = f"{agreement['tenant_id']}:{agreement['agreement_id']}:v{agreement['agreement_version']}"
    if len(binding) > 250:
        raise ValueError("EXTERNAL_ID_TOO_LONG")
    return {
        "schema": SCHEMA, "mode": "OBSERVE",
        "provider": "documenso", "method": "POST",
        "endpoint": "/api/v2/envelope/create",
        "content_type": "multipart/form-data", "json_field": "payload",
        "file_field": "files", "pdf_mimetype": "application/pdf",
        "pdf_sha256": proposed["approved_pdf_sha256"],
        "external_id": binding,
        "payload": {
            "type": "DOCUMENT", "title": title.strip(),
            "externalId": binding, "recipients": recipients,
            "visibility": "ADMIN",
        },
        "pdf_parser_verified": False,
        "signature_placement_visually_verified": False,
        "create_authorized": False, "distribute_authorized": False,
        "execution_authority": "none",
    }


def parse_authenticated_envelope(response: Mapping, *, expected_id: str,
                                  expected_external_id: str,
                                  expected_signer_emails: tuple[str,str]) -> dict:
    """Requires caller to verify provider authentication and TLS separately.

    Parsed response can NEVER on its own verify final artifact or revenue.
    """
    if not isinstance(response, Mapping):
        raise ValueError("PROVIDER_RESPONSE_NOT_OBJECT")
    if not isinstance(expected_id, str) or not ENVELOPE.fullmatch(expected_id):
        raise ValueError("BAD_EXPECTED_ENVELOPE")
    if (response.get("id") != expected_id or response.get("externalId") != expected_external_id
            or response.get("type") != "DOCUMENT"):
        raise ValueError("PROVIDER_DOCUMENT_BINDING_MISMATCH")
    if response.get("status") not in {"DRAFT", "PENDING", "COMPLETED", "REJECTED", "CANCELLED"}:
        raise ValueError("UNRECOGNISED_PROVIDER_STATUS")
    people = response.get("recipients")
    if not isinstance(people, list):
        raise ValueError("PROVIDER_SIGNERS_MISSING")
    matched = [r for r in people if isinstance(r, Mapping) and r.get("role") == "SIGNER"]
    emails = {r.get("email", "").casefold() for r in matched if isinstance(r.get("email"), str)}
    if (not isinstance(expected_signer_emails, tuple) or len(expected_signer_emails) != 2
            or not all(isinstance(x, str) and EMAIL.fullmatch(x) for x in expected_signer_emails)
            or len(matched) != 2 or emails != {x.casefold() for x in expected_signer_emails}):
        raise ValueError("PROVIDER_SIGNERS_NOT_BOUND_TO_AGREEMENT")
    if response["status"] == "COMPLETED":
        if (not timestamp(response.get("completedAt"))
            or any(r.get("signingStatus") != "SIGNED"
                   or not timestamp(r.get("signedAt")) for r in matched)):
            raise ValueError("SIGNING_COMPLETION_NOT_PROVED")
    return {
        "schema": SCHEMA, "mode": "OBSERVE",
        "provider": "documenso", "envelope_id": expected_id,
        "external_id": expected_external_id,
        "provider_status": response["status"],
        "all_signers_marked_signed": response["status"] == "COMPLETED",
        "signed_pdf_independently_verified": False,
        "audit_trail_verified": False, "contract_accepted": False,
        "canonical_registration_authorized": False,
        "payment_observed": False, "revenue_recognized": False,
        "execution_authority": "none",
    }
