"""Bounded immutable Buyer Scout evidence -> canonical Hunter identity.

No crawl, SMTP, review approval or external action. Callers must explicitly
supply internal write authority. Live revalidation, Hunter writes and projection
share one canonical EmpireDB transaction.
"""
from __future__ import annotations

from contextlib import nullcontext
from dataclasses import replace
from datetime import datetime
import math
import re
from typing import Any
from types import SimpleNamespace
from urllib.parse import urlencode, urlsplit
from uuid import UUID, uuid5

from empire_os.buyer_discovery import classify_decision_role, verify_contact_plan
from empire_os.hunter.domain_intelligence import DomainIntelligenceReport
from empire_os.hunter.evidence_graph import (
    HunterFactRow, build_evidence_plan, evidence_hash, normalize_person_name,
)
from empire_os.hunter.materializer import SupabaseHunterMaterializer
from empire_os.hunter.models import ContactEvidence, DomainPattern, VerificationState
from empire_os.identity_promoter import ENTITY_NAMESPACE
from empire_os.sb import request_json, empiredb_transaction
from empire_os.mx_validator import DISPOSABLE_DOMAINS, ROLE_PREFIXES


class BridgeBlocked(ValueError):
    """A deterministic evidence/identity blocker, safe to report without secrets."""


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _domain(value: Any) -> str:
    value = _text(value).lower()
    parsed = urlsplit(value if "://" in value else "https://" + value)
    host = (parsed.hostname or "").removeprefix("www.").rstrip(".")
    if not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", host) or "." not in host:
        raise BridgeBlocked("INVALID_FIRST_PARTY_DOMAIN")
    return host


def _people(evidence: dict) -> list[dict]:
    site = evidence.get("site_evidence")
    raw = site.get("first_party_people") if isinstance(site, dict) else None
    if not isinstance(raw, list):
        return []
    accepted = {}
    identities = {}
    emails = {}
    for person in raw:
        if not isinstance(person, dict) or not all(
            person.get(key) is True for key in (
                "person_explicitly_named", "email_directly_bound_to_person", "mx_verified",
            )
        ):
            continue
        if person.get("source") != "first_party_site" or not all(
            _text(person.get(key)) for key in ("name", "title", "email", "source_url")
        ):
            continue
        try:
            confidence = float(person["mx_confidence"])
        except (KeyError, TypeError, ValueError):
            continue
        if not math.isfinite(confidence) or not 0 <= confidence <= 1:
            continue
        row = {**person, "mx_confidence": confidence}
        name = normalize_person_name(row["name"])
        email = row["email"].strip().lower()
        if not name or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
            continue
        # A normalized name is only an entity-scoped lookup key, never proof
        # that conflicting immutable observations describe the same human.
        local, email_domain = email.rsplit("@", 1)
        if local in ROLE_PREFIXES or email_domain in DISPOSABLE_DOMAINS:
            continue
        identity = (row["name"].strip(), row["title"].strip(), email)
        if name in identities and identities[name] != identity:
            raise BridgeBlocked("AMBIGUOUS_ACQUISITION_PERSON")
        if email in emails and emails[email] != name:
            raise BridgeBlocked("AMBIGUOUS_ACQUISITION_EMAIL")
        identities[name], emails[email] = identity, name
        key = (name, email, row["source_url"])
        if key not in accepted or confidence > accepted[key]["mx_confidence"]:
            accepted[key] = row
    return [accepted[key] for key in sorted(accepted)]


def materialize_buyer_scout_identity(
    *, prospect_id: str, write_authorized: bool,
    request_factory=request_json, transaction_factory=None,
) -> dict[str, Any]:
    """Resolve one prospect using immutable evidence read inside the live unit.

    ``transaction_factory`` is an injectable context-manager factory yielding
    a scoped request callable. Live custom transports must supply it explicitly;
    there is no non-atomic live fallback. OBSERVE uses only ``request_factory``.
    """
    stage = "transaction_begin"
    scoped_request = None
    committed = False
    attempted = False
    mutated = False
    result: dict[str, Any] = {
        "ok": False, "prospect_id": prospect_id, "mode": "OBSERVE",
        "write_authorized": write_authorized is True,
        "internal_mutation_performed": False, "external_execution_performed": False,
        "outbound_actions": False, "payment_actions": False, "revenue_actions": False,
        "decision_maker": None, "projection_performed": False,
    }

    def request(method, path, **kwargs):
        nonlocal attempted, mutated, stage
        stage = urlsplit(path).path.rsplit("/", 1)[-1]
        if method != "GET":
            if write_authorized is not True:
                raise BridgeBlocked("WRITE_NOT_AUTHORIZED")
            attempted = True
        rows = scoped_request(method, path, **kwargs)
        if method != "GET" and rows:
            mutated = True
        return rows

    def get(table, **params):
        rows = request("GET", f"/rest/v1/{table}?{urlencode(params)}")
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise BridgeBlocked("INVALID_CANONICAL_RESPONSE")
        return rows

    def write(method, table, payload, **params):
        return request(
            method, f"/rest/v1/{table}?{urlencode(params)}", payload=payload,
            prefer="resolution=ignore-duplicates,return=representation"
            if method == "POST" else "return=representation",
        )

    try:
        if write_authorized is True:
            if transaction_factory is None:
                if request_factory is not request_json:
                    raise BridgeBlocked("ATOMIC_TRANSACTION_REQUIRED")
                transaction_factory = empiredb_transaction
            context = transaction_factory()
        else:
            context = nullcontext(request_factory)
        with context as scoped_request:
            pid = str(UUID(prospect_id))
            prospects = get("prospects", select="business_name,website,contact_name,contact_title,contact_source,contacted_status", id=f"eq.{pid}", limit=2)
            if len(prospects) != 1:
                raise BridgeBlocked("CANONICAL_PROSPECT_NOT_FOUND")
            prospect = prospects[0]
            acquisitions = get(
                "prospect_acquisitions", select="id,evidence,created_at,ingest_key", prospect_id=f"eq.{pid}",
                source="eq.buyer_scout_review_ready", order="created_at.desc,id.desc", limit=1,
            )
            if not acquisitions:
                raise BridgeBlocked("NO_BUYER_SCOUT_ACQUISITION")
            acquisition = acquisitions[0]
            evidence = acquisition.get("evidence")
            if not isinstance(evidence, dict):
                raise BridgeBlocked("INVALID_ACQUISITION_EVIDENCE")
            people = _people(evidence)
            if not people:
                raise BridgeBlocked("NO_VERIFIED_FIRST_PARTY_PERSON")
            domain = _domain(evidence.get("domain"))
            website = _text(prospect.get("website"))
            if _domain(website) != domain or _domain(evidence.get("source_url")) != domain:
                raise BridgeBlocked("ACQUISITION_DOMAIN_CONFLICT")
            if any(_domain(person["source_url"]) != domain for person in people):
                raise BridgeBlocked("PERSON_SOURCE_DOMAIN_CONFLICT")
            observed_at = datetime.fromisoformat(acquisition["created_at"].replace("Z", "+00:00"))
            if observed_at.tzinfo is None:
                raise BridgeBlocked("ACQUISITION_TIMESTAMP_REQUIRED")
            if not acquisition.get("id"):
                raise BridgeBlocked("ACQUISITION_ID_REQUIRED")
            provenance = {
                "source": "buyer_scout", "prospect_id": pid, "domain": domain,
                "source_url": evidence["source_url"], "ingest_key": acquisition.get("ingest_key"),
                "acquisition_id": acquisition.get("id"),
                "evidence_ref": f"canonical:prospect_acquisitions:{acquisition.get('id')}",
            }
            links = get("prospect_entity_links", select="entity_id,active", prospect_id=f"eq.{pid}", limit=2)
            if links and (len(links) != 1 or links[0].get("active") is not True or not links[0].get("entity_id")):
                raise BridgeBlocked("AMBIGUOUS_PROSPECT_ENTITY_LINK")
            new_entity = False
            if links:
                eid = str(UUID(links[0]["entity_id"]))
                entities = get("business_entities", select="canonical_website", id=f"eq.{eid}", limit=2)
                if len(entities) != 1:
                    raise BridgeBlocked("LINKED_ENTITY_NOT_FOUND")
                if _domain(entities[0].get("canonical_website")) != domain:
                    raise BridgeBlocked("LINKED_ENTITY_DOMAIN_CONFLICT")
            else:
                # Broad indexed name matches are not identity. Filter candidate
                # websites by exact parsed host and reject truncated search results.
                entities = get("business_entities", select="id,canonical_website", canonical_website=f"ilike.*{domain}*", limit=1000)
                if len(entities) >= 1000:
                    raise BridgeBlocked("ENTITY_SEARCH_INCOMPLETE")
                matches = []
                for entity in entities:
                    try:
                        if _domain(entity.get("canonical_website")) == domain:
                            matches.append(entity)
                    except BridgeBlocked:
                        continue
                if len(matches) > 1:
                    raise BridgeBlocked("AMBIGUOUS_BUSINESS_ENTITY")
                new_entity = not matches
                eid = str(UUID(matches[0]["id"])) if matches else str(uuid5(ENTITY_NAMESPACE, f"buyer_scout:domain:{domain}"))
            result["entity_id"] = eid
            contacts = tuple(ContactEvidence(
                email=p["email"].strip(), state=VerificationState.CONFIRMED,
                confidence=p["mx_confidence"], source=p["source"], source_url=p["source_url"],
                person_name=p["name"].strip(), person_title=p["title"].strip(),
                person_bound=True, first_party=True, mx_ok=True, syntax_ok=True,
            ) for p in people)
            report = DomainIntelligenceReport(
                requested_url=evidence["source_url"], domain=domain,
                business_names=(_text(prospect.get("business_name")),), contacts=contacts,
                pattern=DomainPattern(domain, None, 0, 0.0, 0.0), pages_checked=0,
                evidence_score=min(p["mx_confidence"] for p in people), source="buyer_scout",
            )
            plan = build_evidence_plan(report, entity_id=eid, observed_at=observed_at)
            # Preserve the observations in the existing canonical fact writer:
            # contact tables do not have a source_url / acquisition provenance column.
            facts = tuple(HunterFactRow(
                entity_id=eid, fact_key="buyer_scout_first_party_person",
                fact_value={**provenance, **p}, confidence=p["mx_confidence"],
                first_seen_at=plan.observed_at, last_seen_at=plan.observed_at,
                evidence_uri=p["source_url"],
                evidence_hash=evidence_hash(eid, provenance, p),
            ) for p in people)
            confidence_by_name = {normalize_person_name(p["name"]): p["mx_confidence"] for p in people}
            plan = replace(plan, facts=facts, people=tuple(
                replace(p, identity_confidence=confidence_by_name[p.normalized_name]) for p in plan.people
            ))
            economic = {normalize_person_name(p["name"]): p for p in people
                        if classify_decision_role(p["title"])[0] == "economic_buyer"}
            top_score = max((classify_decision_role(p["title"])[1] for p in economic.values()), default=0)
            top = [p for p in economic.values() if classify_decision_role(p["title"])[1] == top_score]
            decision = top[0] if len(top) == 1 else None
            result["decision_status"] = "RESOLVED" if decision else "AMBIGUOUS_DECISION_MAKER" if top else "NO_ECONOMIC_BUYER"
            result["decision_candidates"] = sorted(p["name"] for p in top)
            result["people_count"] = len(plan.people)
            if write_authorized is True:
                if new_entity:
                    name = _text(prospect.get("business_name"))
                    if not name:
                        raise BridgeBlocked("BUSINESS_NAME_REQUIRED")
                    write("POST", "business_entities", {
                        "id": eid, "canonical_name": name, "normalized_name": name.lower(),
                        "canonical_website": website, "provenance": provenance,
                        "resolution_state": "resolved_candidate",
                        "identity_confidence": report.evidence_score,
                    }, on_conflict="id")
                    persisted = get("business_entities", select="canonical_website", id=f"eq.{eid}", limit=2)
                    if len(persisted) != 1 or _domain(persisted[0].get("canonical_website")) != domain:
                        raise BridgeBlocked("ENTITY_INSERT_CONFLICT")
                if not links:
                    write("POST", "prospect_entity_links", {
                        "prospect_id": pid, "entity_id": eid, "active": True,
                        "match_method": "buyer_scout_exact_domain", "match_score": report.evidence_score,
                        "evidence": provenance,
                    }, on_conflict="prospect_id")
                    persisted = get("prospect_entity_links", select="entity_id,active", prospect_id=f"eq.{pid}", limit=2)
                    if len(persisted) != 1 or persisted[0].get("entity_id") != eid or persisted[0].get("active") is not True:
                        raise BridgeBlocked("PROSPECT_ENTITY_LINK_CONFLICT")
            result["materializer"] = SupabaseHunterMaterializer(
                request_factory=request, deterministic_person_ids=True,
            ).materialize(
                plan, write_authorized=write_authorized is True,
            )
            result["review_input"] = {
                "review_ready": False, "outreach_ready": False,
                "rejection_reason": result["decision_status"],
            }
            if write_authorized is True:
                for contact in plan.contacts:
                    person_id = result["materializer"]["person_ids"][contact.person_normalized_name]
                    canonical = get(
                        "intelligence_contact_points", select="person_id,verification_state",
                        entity_id=f"eq.{eid}", contact_type="eq.work_email",
                        normalized_value=f"eq.{contact.normalized_value}", limit=1000,
                    )
                    if len(canonical) >= 1000 or any(
                        row.get("verification_state") in {"invalid", "suppressed"}
                        or row.get("person_id") not in (None, person_id) for row in canonical
                    ):
                        raise BridgeBlocked("CANONICAL_CONTACT_CONFLICT")
                    if not any(row.get("person_id") == person_id and row.get("verification_state") == "verified" for row in canonical):
                        raise BridgeBlocked("CANONICAL_VERIFIED_CONTACT_REQUIRED")
                for fact in plan.facts:
                    persisted = get("intelligence_facts", select="entity_type,entity_id,fact_key,fact_value,source_id,evidence_uri",
                                    evidence_hash=f"eq.{fact.evidence_hash}", limit=2)
                    if len(persisted) != 1 or any((
                        persisted[0].get("entity_type") != "company",
                        persisted[0].get("entity_id") != eid,
                        persisted[0].get("evidence_uri") != fact.evidence_uri,
                        persisted[0].get("fact_key") != fact.fact_key,
                        persisted[0].get("fact_value") != fact.fact_value,
                        persisted[0].get("source_id") != result["materializer"]["source_id"],
                    )):
                        raise BridgeBlocked("CANONICAL_FACT_CONFLICT")
            if decision:
                result["decision_maker"] = {**decision, "decision_role": "economic_buyer", "decision_score": top_score}
                if write_authorized is True:
                    person_id = result["materializer"]["person_ids"][normalize_person_name(decision["name"])]
                    result["decision_maker"]["person_id"] = person_id
                    # Use the existing review contact policy with immutable observed
                    # MX evidence as its validator. No network verification occurs.
                    observed = SimpleNamespace(
                        validate=lambda email: SimpleNamespace(
                            email=email, is_valid=True, confidence=decision["mx_confidence"],
                            has_mx=True, smtp_accepts=False, is_role_address=False, is_disposable=False,
                        ),
                    )
                    result["review_input"] = verify_contact_plan({
                        "decision_maker": result["decision_maker"],
                        "decision_reconciliation": {"review_required": False},
                        "contact_candidates": [{
                            "email": decision["email"].strip().lower(), "source": "official_site",
                            "source_url": decision["source_url"], "bound_to_decision_maker": True,
                            "confidence": decision["mx_confidence"], "has_mx": True,
                        }],
                    }, validator=observed)
                # Person fields establish a projection; acquisition provenance alone does not.
                if any(prospect.get(key) for key in ("contact_name", "contact_title")):
                    result["projection_status"] = "EXISTING_PROJECTION_PRESERVED"
                    if normalize_person_name(prospect.get("contact_name")) != normalize_person_name(decision["name"]):
                        result["review_input"] = {
                            "review_ready": False, "outreach_ready": False,
                            "rejection_reason": "EXISTING_DECISION_MAKER_CONFLICT",
                        }
                elif write_authorized is True:
                    patched = write("PATCH", "prospects", {
                        "contact_name": decision["name"].strip(), "contact_title": decision["title"].strip(),
                        "contact_source": "buyer_scout_canonical_first_party:" + decision["source_url"],
                    }, id=f"eq.{pid}", **{key: "is.null" if prospect.get(key) is None else f"eq.{prospect[key]}"
                       for key in ("contact_name", "contact_title", "contact_source")})
                    result["projection_performed"] = bool(patched)
                    result["projection_status"] = "PROJECTED" if patched else "CONCURRENT_PROJECTION_PRESERVED"
                    if not patched:
                        raise BridgeBlocked("CONCURRENT_PROJECTION_PRESERVED")
            if write_authorized is True:
                final = get("prospects", select="contact_name,contact_title,contact_source,contacted_status",
                            id=f"eq.{pid}", limit=2)
                if len(final) != 1 or final[0].get("contacted_status") != prospect.get("contacted_status"):
                    raise BridgeBlocked("CANONICAL_PROSPECT_READBACK_CONFLICT")
                if result["projection_performed"] and (
                    final[0].get("contact_name") != decision["name"].strip()
                    or final[0].get("contact_title") != decision["title"].strip()
                    or final[0].get("contact_source") != "buyer_scout_canonical_first_party:" + decision["source_url"]
                ):
                    raise BridgeBlocked("CANONICAL_PROJECTION_READBACK_CONFLICT")
            stage = "commit"
            result.update(ok=True, status="CANONICALIZED" if write_authorized is True else "OBSERVE", retryable=False)
        committed = write_authorized is True
    except BridgeBlocked as exc:
        result.update(ok=False, status=str(exc), blocker=str(exc), error_type=type(exc).__name__, retryable=True)
    except Exception as exc:
        # Request errors can contain credentials or response data; do not echo.
        result.update(ok=False, status="CANONICAL_PERSON_BRIDGE_FAILED", blocker="CANONICAL_PERSON_BRIDGE_FAILED",
                      error_type=type(exc).__name__, retryable=True)
        if getattr(exc, "sqlstate", None) in {"40001", "40P01"}:
            result["status"] = result["blocker"] = "CANONICAL_TRANSACTION_RETRY_REQUIRED"
    gateway = getattr(scoped_request, "gateway", None)
    transaction_state = getattr(gateway, "transaction_state", None)
    if write_authorized is not True:
        transaction_state = "not_started"
    elif transaction_state is None:
        transaction_state = "committed" if committed else "rolled_back" if scoped_request else "not_started"
    write_outcome_unknown = bool(getattr(gateway, "write_outcome_unknown", False))
    result["transaction_state"] = transaction_state
    result["failure_stage"] = None if result["ok"] else stage
    if not result["ok"]:
        result["projection_performed"] = False
        result["review_input"] = {"review_ready": False, "outreach_ready": False,
                                  "rejection_reason": result["blocker"]}
        if write_outcome_unknown:
            result["status"] = result["blocker"] = "CANONICAL_TRANSACTION_OUTCOME_UNKNOWN"
            result["recovery_action"] = "RETRY_CANONICAL_REVALIDATION"
    result["mode"] = "AUTO_INTERNAL" if write_authorized is True else "OBSERVE"
    result["internal_write_attempted"] = attempted
    result["write_outcome_unknown"] = write_outcome_unknown
    result["internal_mutation_performed"] = None if write_outcome_unknown else bool(committed and mutated)
    return result
