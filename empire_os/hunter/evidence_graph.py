"""Map Empire Hunter observations into canonical Intelligence Fabric rows."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from empire_os.hunter.domain_intelligence import DomainIntelligenceReport
from empire_os.hunter.models import VerificationState


def _uuid(value: str, *, field: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError(f"invalid {field}") from exc


def normalize_person_name(value: str) -> str:
    return " ".join(
        re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).split()
    )


def normalize_title(value: str) -> str:
    return " ".join(
        re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).split()
    )


def evidence_hash(*parts: object) -> str:
    canonical = json.dumps(
        parts,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


@dataclass(frozen=True)
class HunterPersonRow:
    canonical_name: str
    normalized_name: str
    identity_confidence: float


@dataclass(frozen=True)
class HunterEmploymentRow:
    person_normalized_name: str
    entity_id: str
    title: str
    normalized_title: str
    is_current: bool
    confidence: float
    evidence_uri: str | None


@dataclass(frozen=True)
class HunterContactRow:
    person_normalized_name: str | None
    entity_id: str
    contact_type: str
    value: str
    normalized_value: str
    verification_state: str
    confidence: float
    first_seen_at: str
    last_seen_at: str
    verified_at: str | None
    evidence_uri: str | None


@dataclass(frozen=True)
class HunterFactRow:
    entity_id: str
    fact_key: str
    fact_value: dict[str, Any]
    confidence: float
    first_seen_at: str
    last_seen_at: str
    evidence_uri: str | None
    evidence_hash: str


@dataclass(frozen=True)
class HunterEvidencePlan:
    entity_id: str
    source_key: str
    source_type: str
    source_display_name: str
    source_authority_score: float
    people: tuple[HunterPersonRow, ...]
    employments: tuple[HunterEmploymentRow, ...]
    contacts: tuple[HunterContactRow, ...]
    facts: tuple[HunterFactRow, ...]
    observed_at: str
    write_authorized: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "source": {
                "source_key": self.source_key,
                "source_type": self.source_type,
                "display_name": self.source_display_name,
                "authority_score": self.source_authority_score,
            },
            "people": [asdict(row) for row in self.people],
            "employments": [
                asdict(row) for row in self.employments
            ],
            "contacts": [asdict(row) for row in self.contacts],
            "facts": [asdict(row) for row in self.facts],
            "observed_at": self.observed_at,
            "write_authorized": self.write_authorized,
        }


def build_evidence_plan(
    report: DomainIntelligenceReport,
    *,
    entity_id: str,
    observed_at: datetime | None = None,
) -> HunterEvidencePlan:
    eid = _uuid(entity_id, field="entity_id")
    when = observed_at or datetime.now(timezone.utc)
    if when.tzinfo is None:
        raise ValueError("observed_at must include timezone")
    when_iso = when.astimezone(timezone.utc).isoformat()

    people_by_name: dict[str, HunterPersonRow] = {}
    employment_by_key: dict[
        tuple[str, str], HunterEmploymentRow
    ] = {}
    contacts: list[HunterContactRow] = []

    for item in report.contacts:
        normalized_name = normalize_person_name(
            item.person_name or ""
        )
        if item.person_bound and normalized_name:
            people_by_name.setdefault(
                normalized_name,
                HunterPersonRow(
                    canonical_name=str(item.person_name),
                    normalized_name=normalized_name,
                    identity_confidence=min(
                        0.99,
                        max(0.5, float(item.confidence)),
                    ),
                ),
            )
            if item.person_title:
                key = (
                    normalized_name,
                    normalize_title(item.person_title),
                )
                employment_by_key.setdefault(
                    key,
                    HunterEmploymentRow(
                        person_normalized_name=normalized_name,
                        entity_id=eid,
                        title=str(item.person_title),
                        normalized_title=key[1],
                        is_current=True,
                        confidence=float(item.confidence),
                        evidence_uri=item.source_url,
                    ),
                )

        contacts.append(
            HunterContactRow(
                person_normalized_name=(
                    normalized_name
                    if item.person_bound and normalized_name
                    else None
                ),
                entity_id=eid,
                contact_type="work_email",
                value=item.email,
                normalized_value=item.email.lower(),
                verification_state=(
                    "verified"
                    if item.state is VerificationState.CONFIRMED
                    else "invalid"
                    if item.state is VerificationState.REJECTED
                    else "observed"
                ),
                confidence=float(item.confidence),
                first_seen_at=when_iso,
                last_seen_at=when_iso,
                verified_at=(
                    when_iso
                    if item.state is VerificationState.CONFIRMED
                    else None
                ),
                evidence_uri=item.source_url,
            )
        )

    facts: list[HunterFactRow] = []
    if report.pattern.learned:
        fact_value = report.pattern.as_dict()
        facts.append(
            HunterFactRow(
                entity_id=eid,
                fact_key="email_domain_pattern",
                fact_value=fact_value,
                confidence=float(report.pattern.confidence),
                first_seen_at=when_iso,
                last_seen_at=when_iso,
                evidence_uri=report.requested_url,
                evidence_hash=evidence_hash(
                    "company",
                    eid,
                    "email_domain_pattern",
                    fact_value,
                    report.requested_url,
                ),
            )
        )

    domain = report.domain or "unknown"
    return HunterEvidencePlan(
        entity_id=eid,
        source_key=f"empire_hunter:first_party:{domain}",
        source_type="company_web",
        source_display_name=f"Empire Hunter — {domain}",
        source_authority_score=0.95,
        people=tuple(people_by_name.values()),
        employments=tuple(employment_by_key.values()),
        contacts=tuple(contacts),
        facts=tuple(facts),
        observed_at=when_iso,
    )
