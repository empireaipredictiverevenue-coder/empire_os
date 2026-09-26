"""First-party domain and decision-maker intelligence for Empire Hunter."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Callable

from empire_os.hunter.models import ContactEvidence, DomainPattern, VerificationState
from empire_os.hunter.pattern_brain import (
    PATTERNS,
    generate_candidate,
    learn_domain_pattern,
    normalize_domain,
)
from empire_os.hunter.verification_mesh import VerificationMesh
from empire_os.search_fabric.site_probe import probe_site


@dataclass(frozen=True)
class DomainIntelligenceReport:
    requested_url: str
    domain: str
    business_names: tuple[str, ...]
    contacts: tuple[ContactEvidence, ...]
    pattern: DomainPattern
    pages_checked: int
    evidence_score: float
    source: str = "first_party_site_probe"

    @property
    def confirmed_contacts(self) -> tuple[ContactEvidence, ...]:
        return tuple(
            item for item in self.contacts
            if item.state is VerificationState.CONFIRMED
            and item.person_bound
            and not item.role_address
        )

    @property
    def outreach_ready(self) -> bool:
        return bool(self.confirmed_contacts)

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["contacts"] = [
            item.as_dict() for item in self.contacts
        ]
        data["pattern"] = self.pattern.as_dict()
        data["confirmed_contacts"] = [
            item.as_dict() for item in self.confirmed_contacts
        ]
        data["outreach_ready"] = self.outreach_ready
        return data


ProbeFn = Callable[..., dict[str, Any]]


def _email_domain(email: str) -> str:
    raw = str(email or "").strip().lower()
    return raw.rsplit("@", 1)[1] if "@" in raw else ""


def _first_name(value: str) -> str:
    parts = [
        "".join(ch for ch in token.lower() if ch.isalpha())
        for token in str(value or "").replace("-", " ").split()
    ]
    return next((item for item in parts if item), "")


def _normalize_visible(value: str) -> str:
    return " ".join(
        "".join(
            ch.lower() if ch.isalnum() else " "
            for ch in str(value or "")
        ).split()
    )


def _known_person_page_observations(
    evidence: dict[str, Any],
    mesh: VerificationMesh,
    domain: str,
    known_people: tuple[dict[str, Any], ...],
) -> list[ContactEvidence]:
    rows: list[ContactEvidence] = []
    seen: set[str] = set()

    for person in known_people:
        name = str(person.get("name") or "").strip()
        title = str(person.get("title") or "").strip()
        if not name:
            continue
        normalized_name = _normalize_visible(name)
        normalized_title = _normalize_visible(title)
        candidates = {
            candidate
            for pattern in PATTERNS
            if (
                candidate := generate_candidate(
                    name,
                    domain,
                    pattern,
                )
            )
        }
        if not candidates:
            continue

        for page in evidence.get("pages_checked") or []:
            if not isinstance(page, dict):
                continue
            page_url = str(
                page.get("canonical_url")
                or page.get("url")
                or ""
            ).strip()
            if normalize_domain(page_url) != domain:
                continue
            visible = _normalize_visible(
                page.get("visible_text") or ""
            )
            if (
                not visible
                or normalized_name not in visible
            ):
                continue
            if normalized_title:
                start = visible.find(normalized_name)
                window = visible[
                    max(0, start - 120):
                    start + len(normalized_name) + 220
                ]
                if normalized_title not in window:
                    continue

            page_emails = {
                str(value or "").strip().lower()
                for value in page.get("emails") or []
                if str(value or "").strip()
            }
            matches = sorted(candidates & page_emails)
            if len(matches) != 1:
                continue
            email = matches[0]
            if email in seen:
                continue
            seen.add(email)
            rows.append(
                mesh.verify(
                    email,
                    source="first_party_page_correlation",
                    source_url=page_url or None,
                    person_name=name,
                    person_title=title or None,
                    person_bound=True,
                    first_party=True,
                )
            )

    return rows


def _person_observations(
    evidence: dict[str, Any],
    mesh: VerificationMesh,
    domain: str,
) -> list[ContactEvidence]:
    rows: list[ContactEvidence] = []
    source_url = str(
        evidence.get("final_url")
        or evidence.get("canonical_url")
        or evidence.get("requested_url")
        or ""
    ).strip() or None

    for person in evidence.get("people") or []:
        if not isinstance(person, dict):
            continue
        name = str(person.get("name") or "").strip()
        title = str(person.get("title") or "").strip() or None
        email = str(person.get("email") or "").strip()
        if (
            not name
            or not email
            or _email_domain(email) != domain
        ):
            continue
        rows.append(
            mesh.verify(
                email,
                source="first_party_schema_person",
                source_url=str(person.get("url") or "").strip()
                or source_url,
                person_name=name,
                person_title=title,
                person_bound=True,
                first_party=True,
            )
        )
    return rows


def _generic_site_observations(
    evidence: dict[str, Any],
    mesh: VerificationMesh,
    existing: set[str],
    domain: str,
) -> list[ContactEvidence]:
    rows: list[ContactEvidence] = []
    source_url = str(
        evidence.get("final_url")
        or evidence.get("canonical_url")
        or evidence.get("requested_url")
        or ""
    ).strip() or None

    people_by_first: dict[str, list[dict[str, Any]]] = {}
    for person in evidence.get("people") or []:
        if not isinstance(person, dict):
            continue
        first = _first_name(person.get("name") or "")
        if first:
            people_by_first.setdefault(first, []).append(person)

    for email in evidence.get("emails") or []:
        normalized = str(email or "").strip().lower()
        if (
            not normalized
            or normalized in existing
            or _email_domain(normalized) != domain
        ):
            continue
        local = normalized.split("@", 1)[0]
        matches = people_by_first.get(local, [])
        if len(matches) == 1:
            person = matches[0]
            rows.append(
                mesh.verify(
                    normalized,
                    source="first_party_name_correlation",
                    source_url=str(
                        person.get("url") or ""
                    ).strip() or source_url,
                    person_name=str(
                        person.get("name") or ""
                    ).strip() or None,
                    person_title=str(
                        person.get("title") or ""
                    ).strip() or None,
                    person_bound=True,
                    first_party=True,
                )
            )
            continue

        rows.append(
            mesh.verify(
                normalized,
                source="first_party_site_email",
                source_url=source_url,
                person_bound=False,
                first_party=True,
            )
        )
    return rows


def analyze_domain(
    website: str,
    *,
    mesh: VerificationMesh | None = None,
    probe: ProbeFn = probe_site,
    known_people: tuple[dict[str, Any], ...] = (),
    max_pages: int = 5,
    request_timeout: float = 5.0,
    time_budget_seconds: float = 25.0,
) -> DomainIntelligenceReport:
    verifier = mesh or VerificationMesh()
    evidence = probe(
        website,
        max_pages=max_pages,
        request_timeout=request_timeout,
        time_budget_seconds=time_budget_seconds,
        page_priority="people",
    )
    if not isinstance(evidence, dict) or evidence.get("ok") is not True:
        return DomainIntelligenceReport(
            requested_url=website,
            domain=normalize_domain(website),
            business_names=(),
            contacts=(),
            pattern=DomainPattern(
                domain=normalize_domain(website),
                pattern=None,
                observations=0,
                agreement=0.0,
                confidence=0.0,
            ),
            pages_checked=0,
            evidence_score=0.0,
        )

    domain = normalize_domain(
        str(evidence.get("domain") or website)
    )
    contacts = _person_observations(
        evidence,
        verifier,
        domain,
    )
    contacts.extend(
        _known_person_page_observations(
            evidence,
            verifier,
            domain,
            known_people,
        )
    )
    existing = {item.email for item in contacts}
    contacts.extend(
        _generic_site_observations(
            evidence,
            verifier,
            existing,
            domain,
        )
    )

    pattern = learn_domain_pattern(
        [
            {
                "email": item.email,
                "person_name": item.person_name,
                "person_bound": item.person_bound,
                "first_party": item.first_party,
            }
            for item in contacts
            if item.person_name
        ],
        domain=domain,
    )

    # Learned-pattern candidates are useful evidence but are never promoted
    # to confirmed solely from MX. They remain probable until a stronger
    # first-party/mailbox/delivery observation arrives.
    if pattern.learned:
        known = {item.email for item in contacts}
        for person in evidence.get("people") or []:
            if not isinstance(person, dict):
                continue
            name = str(person.get("name") or "").strip()
            if not name or str(person.get("email") or "").strip():
                continue
            candidate = generate_candidate(
                name,
                domain,
                str(pattern.pattern),
            )
            if not candidate or candidate in known:
                continue
            contacts.append(
                verifier.verify(
                    candidate,
                    source="empire_pattern_brain",
                    source_url=str(
                        person.get("url")
                        or evidence.get("final_url")
                        or ""
                    ).strip()
                    or None,
                    person_name=name,
                    person_title=str(
                        person.get("title") or ""
                    ).strip()
                    or None,
                    person_bound=True,
                    first_party=False,
                )
            )
            known.add(candidate)

    pages = evidence.get("pages_checked") or []
    return DomainIntelligenceReport(
        requested_url=website,
        domain=domain,
        business_names=tuple(
            str(value).strip()
            for value in evidence.get("business_names") or []
            if str(value).strip()
        ),
        contacts=tuple(contacts),
        pattern=pattern,
        pages_checked=len(pages) if isinstance(pages, list) else 0,
        evidence_score=float(evidence.get("evidence_score") or 0.0),
    )
