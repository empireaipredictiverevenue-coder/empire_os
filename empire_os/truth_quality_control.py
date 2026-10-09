from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from difflib import SequenceMatcher
from hashlib import sha256
from typing import Any
from urllib.parse import urlparse
import re


VERDICTS = {
    "PASS",
    "PASS_WITH_WARNINGS",
    "HOLD_FOR_VERIFICATION",
    "REJECT",
    "CONFLICT",
    "DUPLICATE",
    "STALE",
    "INSUFFICIENT_EVIDENCE",
}


SEVERITY_WEIGHT = {
    "INFO": 0,
    "LOW": 1,
    "MEDIUM": 2,
    "HIGH": 3,
    "CRITICAL": 4,
}


GARBAGE_SUFFIXES = (
    ".json",
    ".md",
    ".txt",
    ".py",
    ".sql",
    ".yaml",
    ".yml",
    ".csv",
    ".log",
)


KNOWN_NON_BUYER_DOMAINS = {
    "ahrefs.com",
    "semrush.com",
    "serpapi.com",
    "localfalcon.com",
    "aol.com",
}


ALLOWED_BUYER_TLDS = {
    "com",
    "co",
    "uk",
    "io",
    "ai",
    "net",
    "org",
    "us",
    "ca",
    "biz",
    "info",
    "pro",
    "media",
    "marketing",
    "agency",
    "digital",
    "group",
    "company",
    "services",
    "solutions",
}


@dataclass(frozen=True)
class Detection:
    detection_type: str
    severity: str
    confidence: float
    reason: str
    evidence: list[str] = field(
        default_factory=list
    )
    affected_fields: list[str] = field(
        default_factory=list
    )
    recommended_action: str = "OBSERVE"
    action_allowed: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DetectionDecision:
    entity_type: str
    raw_identity: str
    canonical_identity: str | None
    identity_fingerprint: str | None
    verdict: str
    detections: list[Detection]
    source_independence_count: int = 0
    evidence_count: int = 0
    action_allowed: bool = False

    def as_dict(self) -> dict[str, Any]:

        return {
            "entity_type":
                self.entity_type,

            "raw_identity":
                self.raw_identity,

            "canonical_identity":
                self.canonical_identity,

            "identity_fingerprint":
                self.identity_fingerprint,

            "verdict":
                self.verdict,

            "detections":
                [
                    item.as_dict()
                    for item
                    in self.detections
                ],

            "source_independence_count":
                self.source_independence_count,

            "evidence_count":
                self.evidence_count,

            "action_allowed":
                self.action_allowed,
        }


def now_iso() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def normalize_domain(
    value: str,
) -> str:

    value = (
        value
        or ""
    ).strip().lower()

    if not value:
        return ""

    if "://" in value:

        try:
            value = (
                urlparse(
                    value
                ).hostname
                or value
            )

        except Exception:
            pass

    value = value.split(
        "/",
        1,
    )[0]

    value = value.split(
        ":",
        1,
    )[0]

    value = value.rstrip(".")

    if value.startswith(
        "www."
    ):
        value = value[4:]

    return value


def looks_like_public_domain(
    value: str,
    *,
    allowed_tlds: set[str] | None = None,
) -> bool:

    domain = normalize_domain(
        value
    )

    if (
        not domain
        or "." not in domain
    ):
        return False

    if domain.startswith(
        "empire."
    ):
        return False

    if domain.endswith(
        GARBAGE_SUFFIXES
    ):
        return False

    labels = domain.split(".")

    if len(labels) < 2:
        return False

    if allowed_tlds is not None:

        if labels[-1] not in allowed_tlds:
            return False

    for label in labels:

        if not label:
            return False

        if (
            label.startswith("-")
            or label.endswith("-")
        ):
            return False

        if not re.fullmatch(
            r"[a-z0-9-]+",
            label,
        ):
            return False

    return True


def identity_fingerprint(
    entity_type: str,
    canonical_identity: str,
) -> str:

    raw = (
        entity_type.strip().lower()
        + "|"
        + canonical_identity.strip().lower()
    )

    return sha256(
        raw.encode(
            "utf-8"
        )
    ).hexdigest()


def evidence_fingerprint(
    evidence: str,
) -> str:

    normalized = " ".join(
        (
            evidence
            or ""
        )
        .lower()
        .split()
    )

    return sha256(
        normalized.encode(
            "utf-8"
        )
    ).hexdigest()


def independent_evidence_count(
    evidence_lines: list[str],
) -> int:

    return len(
        {
            evidence_fingerprint(
                line
            )

            for line
            in evidence_lines

            if (
                line
                and line.strip()
            )
        }
    )


def near_duplicate_score(
    left: str,
    right: str,
) -> float:

    left = normalize_domain(
        left
    )

    right = normalize_domain(
        right
    )

    if (
        not left
        or not right
    ):
        return 0.0

    if left == right:
        return 1.0

    return SequenceMatcher(
        None,
        left,
        right,
    ).ratio()


def find_near_duplicates(
    domain: str,
    peers: list[str],
    *,
    threshold: float = 0.90,
) -> list[dict[str, Any]]:

    canonical = normalize_domain(
        domain
    )

    matches = []

    for peer in peers:

        peer_canonical = normalize_domain(
            peer
        )

        if (
            not peer_canonical
            or peer_canonical
            == canonical
        ):
            continue

        score = near_duplicate_score(
            canonical,
            peer_canonical,
        )

        if score < threshold:
            continue

        matches.append(
            {
                "domain":
                    peer_canonical,

                "similarity":
                    round(
                        score,
                        4,
                    ),
            }
        )

    matches.sort(
        key=lambda item: (
            -item[
                "similarity"
            ],
            item[
                "domain"
            ],
        )
    )

    return matches


def input_domain_decision(
    domain: str,
    *,
    peers: list[str] | None = None,
    evidence_lines: list[str] | None = None,
    source_ids: list[str] | None = None,
    known_non_buyers: set[str] | None = None,
    allowed_tlds: set[str] | None = None,
) -> DetectionDecision:

    peers = peers or []
    evidence_lines = evidence_lines or []
    source_ids = source_ids or []
    known_non_buyers = (
        known_non_buyers
        or set()
    )

    canonical = normalize_domain(
        domain
    )

    detections: list[Detection] = []

    evidence_count = (
        independent_evidence_count(
            evidence_lines
        )
    )

    source_count = len(
        {
            item
            for item
            in source_ids
            if item
        }
    )

    if not looks_like_public_domain(
        canonical,
        allowed_tlds=allowed_tlds,
    ):

        detections.append(
            Detection(
                detection_type=
                    "GARBAGE_OR_INVALID_IDENTITY",

                severity=
                    "HIGH",

                confidence=
                    0.99,

                reason=
                    (
                        "Value does not satisfy "
                        "the public domain identity contract."
                    ),

                evidence=[
                    domain
                ],

                affected_fields=[
                    "domain"
                ],

                recommended_action=
                    "QUARANTINE",

                action_allowed=
                    False,
            )
        )

        return DetectionDecision(
            entity_type=
                "company",

            raw_identity=
                domain,

            canonical_identity=
                None,

            identity_fingerprint=
                None,

            verdict=
                "REJECT",

            detections=
                detections,

            source_independence_count=
                source_count,

            evidence_count=
                evidence_count,

            action_allowed=
                False,
        )

    if canonical in known_non_buyers:

        detections.append(
            Detection(
                detection_type=
                    "KNOWN_NON_TARGET",

                severity=
                    "HIGH",

                confidence=
                    1.0,

                reason=
                    (
                        "Identity belongs to a known "
                        "tooling/non-target domain."
                    ),

                evidence=[
                    canonical
                ],

                affected_fields=[
                    "domain"
                ],

                recommended_action=
                    "QUARANTINE",

                action_allowed=
                    False,
            )
        )

    near = find_near_duplicates(
        canonical,
        peers,
    )

    if near:

        detections.append(
            Detection(
                detection_type=
                    "SUSPECT_NEAR_DUPLICATE",

                severity=
                    "MEDIUM",

                confidence=
                    max(
                        item[
                            "similarity"
                        ]
                        for item
                        in near
                    ),

                reason=
                    (
                        "Identity is highly similar to "
                        "another candidate. Fuzzy similarity "
                        "may suggest a match but cannot merge it."
                    ),

                evidence=[
                    (
                        item["domain"]
                        + ":"
                        + str(
                            item[
                                "similarity"
                            ]
                        )
                    )

                    for item
                    in near[:10]
                ],

                affected_fields=[
                    "domain",
                    "canonical_identity",
                ],

                recommended_action=
                    "IDENTITY_RESOLUTION",

                action_allowed=
                    False,
            )
        )

    if evidence_count == 0:

        detections.append(
            Detection(
                detection_type=
                    "MISSING_EVIDENCE",

                severity=
                    "MEDIUM",

                confidence=
                    1.0,

                reason=
                    (
                        "No independent evidence is "
                        "bound to this identity."
                    ),

                evidence=[],

                affected_fields=[
                    "evidence"
                ],

                recommended_action=
                    "VERIFY",

                action_allowed=
                    False,
            )
        )

    elif evidence_count == 1:

        detections.append(
            Detection(
                detection_type=
                    "WEAK_EVIDENCE",

                severity=
                    "LOW",

                confidence=
                    0.90,

                reason=
                    (
                        "Only one independent evidence "
                        "item supports the identity."
                    ),

                evidence=[
                    evidence_lines[0][
                        :300
                    ]
                ],

                affected_fields=[
                    "evidence"
                ],

                recommended_action=
                    "CORROBORATE",

                action_allowed=
                    False,
            )
        )

    if source_count <= 1:

        detections.append(
            Detection(
                detection_type=
                    "LOW_SOURCE_INDEPENDENCE",

                severity=
                    "LOW",

                confidence=
                    0.90,

                reason=
                    (
                        "Evidence does not yet show "
                        "multiple independent source origins."
                    ),

                evidence=
                    source_ids[:5],

                affected_fields=[
                    "source_lineage"
                ],

                recommended_action=
                    "CORROBORATE",

                action_allowed=
                    False,
            )
        )

    verdict = "PASS"

    types = {
        item.detection_type
        for item
        in detections
    }

    if "KNOWN_NON_TARGET" in types:

        verdict = "REJECT"

    elif "SUSPECT_NEAR_DUPLICATE" in types:

        verdict = (
            "HOLD_FOR_VERIFICATION"
        )

    elif "MISSING_EVIDENCE" in types:

        verdict = (
            "INSUFFICIENT_EVIDENCE"
        )

    elif detections:

        verdict = (
            "PASS_WITH_WARNINGS"
        )

    action_allowed = (
        verdict == "PASS"
    )

    return DetectionDecision(
        entity_type=
            "company",

        raw_identity=
            domain,

        canonical_identity=
            canonical,

        identity_fingerprint=
            identity_fingerprint(
                "company",
                canonical,
            ),

        verdict=
            verdict,

        detections=
            detections,

        source_independence_count=
            source_count,

        evidence_count=
            evidence_count,

        action_allowed=
            action_allowed,
    )


def output_decision(
    *,
    domain: str,
    status: str | None,
    evidence: dict[str, Any] | None,
    active_verification: bool,
    source_lineage_present: bool,
    authority: str,
    outbound_authority: bool,
    forecast: Any = None,
) -> DetectionDecision:

    canonical = normalize_domain(
        domain
    )

    evidence = evidence or {}

    detections: list[Detection] = []

    if not looks_like_public_domain(
        canonical,
        allowed_tlds=
            None,
    ):

        detections.append(
            Detection(
                detection_type=
                    "INVALID_OUTPUT_IDENTITY",

                severity=
                    "HIGH",

                confidence=
                    0.99,

                reason=
                    (
                        "Output references an invalid "
                        "or non-public canonical identity."
                    ),

                evidence=[
                    domain
                ],

                affected_fields=[
                    "domain"
                ],

                recommended_action=
                    "REJECT_OUTPUT",

                action_allowed=
                    False,
            )
        )

    buyer_role = bool(
        evidence.get(
            "publisher_program"
        )
        or evidence.get(
            "active_demand"
        )
    )

    if (
        status
        == "READY_TO_APPROACH"
        and not active_verification
    ):

        detections.append(
            Detection(
                detection_type=
                    "UNSUPPORTED_READY_STATE",

                severity=
                    "CRITICAL",

                confidence=
                    1.0,

                reason=
                    (
                        "READY_TO_APPROACH exists without "
                        "active verification provenance."
                    ),

                evidence=[
                    status
                ],

                affected_fields=[
                    "status",
                    "verification"
                ],

                recommended_action=
                    "BLOCK_ACTION",

                action_allowed=
                    False,
            )
        )

    if (
        status
        == "READY_TO_APPROACH"
        and not buyer_role
    ):

        detections.append(
            Detection(
                detection_type=
                    "UNSUPPORTED_BUYER_ROLE",

                severity=
                    "CRITICAL",

                confidence=
                    1.0,

                reason=
                    (
                        "READY_TO_APPROACH exists without "
                        "corroborated buyer/publisher role."
                    ),

                evidence=[
                    str(
                        evidence
                    )[
                        :500
                    ]
                ],

                affected_fields=[
                    "status",
                    "evidence"
                ],

                recommended_action=
                    "BLOCK_ACTION",

                action_allowed=
                    False,
            )
        )

    if not source_lineage_present:

        detections.append(
            Detection(
                detection_type=
                    "MISSING_OUTPUT_LINEAGE",

                severity=
                    "HIGH",

                confidence=
                    1.0,

                reason=
                    (
                        "Output cannot be traced to "
                        "source evidence."
                    ),

                evidence=[],

                affected_fields=[
                    "source_lineage"
                ],

                recommended_action=
                    "HOLD_OUTPUT",

                action_allowed=
                    False,
            )
        )

    if (
        authority.upper()
        in {
            "OBSERVE",
            "FOUNDER_REVIEW_ONLY",
            "NONE",
        }
        and outbound_authority
    ):

        detections.append(
            Detection(
                detection_type=
                    "AUTHORITY_CONFLICT",

                severity=
                    "CRITICAL",

                confidence=
                    1.0,

                reason=
                    (
                        "Output requests outbound authority "
                        "while execution authority is non-live."
                    ),

                evidence=[
                    authority,
                    str(
                        outbound_authority
                    ),
                ],

                affected_fields=[
                    "authority",
                    "outbound_authority"
                ],

                recommended_action=
                    "BLOCK_ACTION",

                action_allowed=
                    False,
            )
        )

    economics_present = bool(
        evidence.get(
            "economics"
        )
    )

    if (
        forecast is not None
        and not economics_present
    ):

        detections.append(
            Detection(
                detection_type=
                    "UNSUPPORTED_ECONOMIC_FORECAST",

                severity=
                    "HIGH",

                confidence=
                    0.99,

                reason=
                    (
                        "Economic forecast is present "
                        "without economics evidence."
                    ),

                evidence=[
                    str(
                        forecast
                    )[
                        :300
                    ]
                ],

                affected_fields=[
                    "forecast",
                    "economics"
                ],

                recommended_action=
                    "HOLD_OUTPUT",

                action_allowed=
                    False,
            )
        )

    verdict = "PASS"

    if detections:

        max_severity = max(
            (
                SEVERITY_WEIGHT.get(
                    item.severity,
                    0,
                )
                for item
                in detections
            ),
            default=0,
        )

        if max_severity >= 4:
            verdict = "CONFLICT"

        elif max_severity >= 3:
            verdict = (
                "HOLD_FOR_VERIFICATION"
            )

        else:
            verdict = (
                "PASS_WITH_WARNINGS"
            )

    action_allowed = (
        verdict == "PASS"
        and outbound_authority
    )

    return DetectionDecision(
        entity_type=
            "commercial_output",

        raw_identity=
            domain,

        canonical_identity=
            (
                canonical
                or None
            ),

        identity_fingerprint=
            (
                identity_fingerprint(
                    "company",
                    canonical,
                )
                if canonical
                else None
            ),

        verdict=
            verdict,

        detections=
            detections,

        source_independence_count=
            0,

        evidence_count=
            sum(
                bool(value)
                for value
                in evidence.values()
            ),

        action_allowed=
            action_allowed,
    )
