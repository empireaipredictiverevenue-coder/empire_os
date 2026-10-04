"""Governed business identity discovery for intent-derived opportunities.

A social profile or post is NEVER treated as first-party company evidence.

The actor may use a public social handle as a bounded discovery key, but a
business identity is verified only when:

1. the upstream Intent Brain decision is RESOLVE_IDENTITY;
2. Search Fabric independently discovers a non-social candidate domain;
3. the candidate first-party site is successfully probed;
4. that first-party site names a person matching the observed social handle;
5. the site exposes a business identity;
6. Empire's existing first-party identity guard supports that domain.

No DB write, canonical promotion, outreach, payment, fulfilment or revenue
authority is granted here.
"""
from __future__ import annotations

import re
from typing import Any, Callable, Iterable, Mapping
from urllib.parse import urlparse

from empire_os.revenue_actor import (
    ActorDescriptor,
    build_actor_envelope,
    validate_actor_envelope,
)
from empire_os.search_fabric.identity_guard import (
    assess_first_party_identity,
)
from empire_os.search_fabric.reliable_search import search_reliable, search_reliable_rows
from empire_os.search_fabric.search import search_resilient
from empire_os.search_fabric.site_probe import probe_site
from empire_os.search_fabric.verification import is_directory_url
from empire_os.search_intelligence.serp import (
    SearchFabricSerpAdapter,
    SerpSnapshotError,
)


DESCRIPTOR = ActorDescriptor(
    actor_key="business_identity",
    actor_version="1.0.0",
    purpose=(
        "Discover and verify a first-party business identity for a "
        "qualified public commercial-intent signal."
    ),
    input_schema="empire.business_identity_request.v1",
    output_schema="empire.business_identity_decision.v1",
    policy_version="business_identity_policy.v1",
    model_version=None,
)


SearchFn = Callable[..., list[dict[str, Any]]]
ProbeFn = Callable[..., Mapping[str, Any]]
GuardFn = Callable[..., Mapping[str, Any]]


_SOCIAL_OR_PLATFORM_HOSTS = {
    "linkedin.com",
    "www.linkedin.com",
    "reddit.com",
    "www.reddit.com",
    "facebook.com",
    "www.facebook.com",
    "instagram.com",
    "www.instagram.com",
    "x.com",
    "www.x.com",
    "twitter.com",
    "www.twitter.com",
    "youtube.com",
    "www.youtube.com",
    "tiktok.com",
    "www.tiktok.com",
}


_GENERIC_SEARCH_NAMES = {
    "linkedin",
    "reddit",
    "facebook",
    "instagram",
    "profile",
    "activity",
    "post",
    "posts",
    "looking",
    "hiring",
    "expert",
    "specialist",
    "freelancer",
    "agency",
}


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split())


def _host(value: Any) -> str:
    try:
        host = urlparse(_clean(value)).netloc.lower()
    except ValueError:
        return ""

    if host.startswith("www."):
        host = host[4:]

    return host.rstrip(".")


def _root_url(value: str) -> str:
    try:
        parsed = urlparse(_clean(value))
    except ValueError:
        return ""

    if parsed.scheme not in {"http", "https"}:
        return ""

    host = parsed.netloc.lower()
    if not host:
        return ""

    return f"{parsed.scheme}://{host}/"


def _linkedin_post_handle(value: str) -> str:
    """Extract the observed author handle from a LinkedIn /posts/ URL."""
    try:
        path = urlparse(_clean(value)).path
    except ValueError:
        return ""

    match = re.search(
        r"/posts/([^/_]+(?:-[^/_]+)*)_",
        path,
        flags=re.I,
    )

    if not match:
        return ""

    return match.group(1).strip().lower()


def _handle_identity_key(handle: str) -> str:
    """Remove LinkedIn's trailing public profile identifier when present."""
    parts = [
        part
        for part in _clean(handle).lower().split("-")
        if part
    ]

    if (
        len(parts) >= 3
        and any(char.isdigit() for char in parts[-1])
    ):
        parts = parts[:-1]

    return re.sub(
        r"[^a-z]",
        "",
        "".join(parts),
    )


def _person_identity_key(name: str) -> str:
    return re.sub(
        r"[^a-z]",
        "",
        _clean(name).lower(),
    )


def _safe_name_seed_from_handle(
    handle: str,
) -> str:
    """Derive a discovery-only human-name seed from structured handles.

    Only hyphen-separated handles with at least two plausible name tokens are
    eligible. Concatenated handles such as ``kimberlysperber`` and opaque
    handles such as ``kumsub`` remain UNKNOWN rather than being guessed.
    """
    parts = [
        part
        for part in _clean(handle)
        .lower()
        .split("-")
        if part
    ]

    if (
        len(parts) >= 3
        and any(
            char.isdigit()
            for char in parts[-1]
        )
    ):
        parts = parts[:-1]

    if not 2 <= len(parts) <= 4:
        return ""

    generic = {
        "linkedin",
        "profile",
        "company",
        "official",
        "marketing",
        "sales",
        "seo",
        "agency",
    }

    if any(
        part in generic
        for part in parts
    ):
        return ""

    if not all(
        re.fullmatch(
            r"[a-z][a-z.'’]*",
            part,
        )
        is not None
        for part in parts
    ):
        return ""

    return " ".join(
        part.capitalize()
        for part in parts
    )


def _discovery_query_plan(
    *,
    handle: str,
    title: str,
) -> list[dict[str, str]]:
    """Build a bounded provenance-bearing discovery plan."""

    plan: list[dict[str, str]] = []

    def add(
        query: str,
        basis: str,
    ) -> None:
        query = _clean(query)

        if not query:
            return

        if any(
            row["query"] == query
            for row in plan
        ):
            return

        plan.append({
            "query": query,
            "basis": basis,
        })

    # Exact observed handle is always allowed as a discovery key.
    add(
        f'"{handle}"',
        "observed_social_handle",
    )

    name_seed = (
        _safe_name_seed_from_handle(
            handle
        )
    )

    if name_seed:
        add(
            f'"{name_seed}"',
            "structured_handle_name_seed",
        )

    # Asking search engines to correlate the exact handle with LinkedIn can
    # recover profile-index evidence while still treating the social source as
    # discovery-only evidence.
    add(
        f'"{handle}" LinkedIn',
        "observed_handle_platform_correlation",
    )

    # The post title is supporting context only. Keep it short and only pair
    # it with a safe derived human-name seed.
    if name_seed and title:
        context_words = [
            word.strip(
                ".,:;!?()[]{}"
            )
            for word in title.split()
        ]

        context_words = [
            word
            for word in context_words
            if len(word) >= 4
        ][:4]

        if context_words:
            add(
                f'"{name_seed}" '
                + " ".join(
                    context_words
                ),
                "name_seed_post_context",
            )

    return plan[:4]


def _person_matches_handle(
    name: str,
    handle: str,
) -> bool:
    person = _person_identity_key(name)
    social = _handle_identity_key(handle)

    if not person or not social:
        return False

    return person == social


def _likely_person_name(value: str) -> bool:
    text = _clean(value).strip(" -|–—")

    words = text.split()

    if not 2 <= len(words) <= 4:
        return False

    lowered = {
        re.sub(r"[^a-z]", "", word.lower())
        for word in words
    }

    if lowered & _GENERIC_SEARCH_NAMES:
        return False

    return all(
        re.fullmatch(
            r"[A-Za-z][A-Za-z.'’\-]*",
            word,
        )
        is not None
        for word in words
    )


def _names_from_search_result(
    row: Mapping[str, Any],
    handle: str,
) -> list[str]:
    """Recover only names that correlate exactly with the social handle."""
    title = _clean(row.get("title"))

    segments = [
        part.strip()
        for part in re.split(
            r"\s+[|–—]\s+|\s+-\s+",
            title,
        )
        if part.strip()
    ]

    names: list[str] = []

    for segment in segments:
        if (
            _likely_person_name(segment)
            and _person_matches_handle(
                segment,
                handle,
            )
        ):
            names.append(segment)

    return list(dict.fromkeys(names))


def _default_search(
    query: str,
    *,
    num: int = 8,
) -> list[dict[str, Any]]:
    """Bounded production identity-discovery search."""
    return search_reliable_rows(
        query,
        num=num,
    )


def _candidate_url_allowed(value: str) -> bool:
    host = _host(value)

    if not host:
        return False

    if host in _SOCIAL_OR_PLATFORM_HOSTS:
        return False

    # RFC-reserved/documentation domains cannot establish
    # commercial first-party identity.
    if (
        host in {
            "example.com",
            "example.org",
            "example.net",
            "localhost",
        }
        or host.endswith(".example")
        or host.endswith(".invalid")
        or host.endswith(".test")
    ):
        return False

    if any(
        host.endswith("." + platform)
        for platform in _SOCIAL_OR_PLATFORM_HOSTS
    ):
        return False

    if is_directory_url(value):
        return False

    return True


def _probe_business_name(
    probe: Mapping[str, Any],
) -> str:
    names = probe.get("business_names") or ()

    for raw in names:
        name = _clean(raw)
        if name:
            return name

    return ""


def _matching_people(
    probe: Mapping[str, Any],
    *,
    handle: str,
    person_names: Iterable[str],
) -> list[dict[str, Any]]:
    explicit_keys = {
        _person_identity_key(name)
        for name in person_names
        if _person_identity_key(name)
    }

    matches: list[dict[str, Any]] = []

    for raw in probe.get("people") or ():
        if not isinstance(raw, Mapping):
            continue

        name = _clean(raw.get("name"))
        title = _clean(raw.get("title"))
        url = _clean(raw.get("url"))

        if not name:
            continue

        key = _person_identity_key(name)

        correlated = (
            _person_matches_handle(
                name,
                handle,
            )
            or (
                key
                and key in explicit_keys
            )
        )

        if not correlated:
            continue

        matches.append({
            "name": name,
            "title": title or None,
            "url": url or None,
        })

    return matches


def _guard_supports_domain(
    guard: Mapping[str, Any],
) -> bool:
    # These are evidence-support fields already exposed by Empire's
    # conservative identity guard. Either may establish support, but neither
    # can override the person-to-site correlation gate above.
    return bool(
        guard.get("discovery_domain_supported") is True
        or guard.get("existing_first_party_support") is True
    )


def run_business_identity_actor(
    payload: Mapping[str, Any],
    *,
    search_fn: SearchFn = _default_search,
    probe_fn: ProbeFn = probe_site,
    guard_fn: GuardFn = assess_first_party_identity,
) -> dict[str, Any]:
    upstream = _clean(
        payload.get("upstream_decision")
        or payload.get("intent_decision")
    )

    source_url = _clean(
        payload.get("source_url")
        or payload.get("url")
    )

    title = _clean(payload.get("title"))
    text = _clean(payload.get("text"))
    niche = _clean(payload.get("niche"))
    metro = _clean(payload.get("metro"))

    blockers: list[str] = []
    supports: list[str] = []
    evidence_refs: list[str] = []

    if source_url:
        evidence_refs.append(source_url)

    if upstream != "RESOLVE_IDENTITY":
        decision = "NOT_ELIGIBLE"
        next_action = "none"
        blockers.append(
            "upstream_intent_not_approved_for_business_identity"
        )

        output = {
            "source_handle": None,
            "source_person_names": [],
            "business_identity_verified": False,
            "business_name": None,
            "website": None,
            "first_party_site_verified": False,
            "candidate_count": 0,
            "candidates": [],
        }

    else:
        handle = _linkedin_post_handle(
            source_url
        )

        if not handle:
            decision = "BUSINESS_IDENTITY_UNRESOLVED"
            next_action = "hold_for_business_identity_evidence"
            blockers.append(
                "source_author_handle_unresolved"
            )

            output = {
                "source_handle": None,
                "source_person_names": [],
                "business_identity_verified": False,
                "business_name": None,
                "website": None,
                "first_party_site_verified": False,
                "candidate_count": 0,
                "candidates": [],
            }

        else:
            supports.append(
                "observed_social_author_handle"
            )

            person_names: list[str] = []
            search_rows: list[dict[str, Any]] = []
            discovery_provider_degraded = False
            discovery_success_observed = False

            query_plan = _discovery_query_plan(
                handle=handle,
                title=title,
            )

            for query_item in query_plan:
                query = query_item["query"]

                try:
                    rows = search_fn(
                        query,
                        num=8,
                    )
                except Exception:
                    rows = []
                    discovery_provider_degraded = True

                if rows:
                    discovery_success_observed = True

                for row in rows or ():
                    if not isinstance(
                        row,
                        Mapping,
                    ):
                        continue

                    normalized = dict(row)
                    search_rows.append(
                        normalized
                    )

                    person_names.extend(
                        _names_from_search_result(
                            normalized,
                            handle,
                        )
                    )

            if (
                not search_rows
                and search_fn is _default_search
            ):
                for query_item in query_plan:
                    try:
                        diagnostic = (
                            search_reliable(
                                query_item["query"],
                                num=8,
                                use_cache=True,
                            )
                        )
                    except Exception:
                        discovery_provider_degraded = True
                        continue

                    diagnostic_state = (
                        diagnostic.get(
                            "searchParameters",
                            {},
                        ).get(
                            "search_state"
                        )
                    )

                    if diagnostic_state == (
                        "PROVIDER_DEGRADED"
                    ):
                        discovery_provider_degraded = True

                    diagnostic_rows = (
                        diagnostic.get(
                            "organic",
                            [],
                        )
                        or []
                    )

                    if diagnostic_rows:
                        discovery_success_observed = True

                        for row in diagnostic_rows:
                            if not isinstance(
                                row,
                                Mapping,
                            ):
                                continue

                            normalized = dict(row)

                            search_rows.append(
                                normalized
                            )

                            person_names.extend(
                                _names_from_search_result(
                                    normalized,
                                    handle,
                                )
                            )

            person_names = list(
                dict.fromkeys(person_names)
            )

            # A person name observed in an actual search result can support one
            # additional bounded business-context discovery pass.
            for person_name in person_names[:2]:
                query = (
                    f'"{person_name}" '
                    f'{niche or "company"}'
                )

                try:
                    extra = search_fn(
                        query,
                        num=8,
                    )
                except Exception:
                    extra = []

                for row in extra or ():
                    if isinstance(row, Mapping):
                        search_rows.append(
                            dict(row)
                        )

            candidate_roots: list[str] = []

            for row in search_rows:
                candidate = _clean(
                    row.get("url")
                    or row.get("link")
                )

                if not _candidate_url_allowed(
                    candidate
                ):
                    continue

                root = _root_url(candidate)

                if (
                    root
                    and root not in candidate_roots
                ):
                    candidate_roots.append(root)

            # Keep public discovery bounded while allowing ambiguity to
            # surface as NEEDS_REVIEW rather than silently selecting the first
            # plausible same-name business.
            candidate_roots = candidate_roots[:4]

            candidates: list[dict[str, Any]] = []

            for root in candidate_roots:
                try:
                    probe = probe_fn(
                        root,
                        max_pages=4,
                        request_timeout=4.0,
                        time_budget_seconds=8.0,
                        page_priority="people",
                    )
                except Exception:
                    probe = {
                        "ok": False,
                        "error": "site_probe_failed",
                    }

                if (
                    not isinstance(probe, Mapping)
                    or probe.get("ok") is not True
                ):
                    candidates.append({
                        "website": root,
                        "verified": False,
                        "reason": "site_probe_failed",
                    })
                    continue

                business_name = _probe_business_name(
                    probe
                )

                people = _matching_people(
                    probe,
                    handle=handle,
                    person_names=person_names,
                )

                if not business_name:
                    candidates.append({
                        "website": root,
                        "verified": False,
                        "reason":
                            "first_party_business_name_missing",
                        "matching_people": people,
                    })
                    continue

                if not people:
                    candidates.append({
                        "website": root,
                        "business_name":
                            business_name,
                        "verified": False,
                        "reason":
                            "source_person_not_confirmed_on_first_party_site",
                    })
                    continue

                try:
                    guard = guard_fn(
                        prospect={
                            "business_name":
                                business_name,
                            "metro": metro,
                            "niche": niche,
                        },
                        candidate_url=root,
                        probe=dict(probe),
                    )
                except Exception:
                    guard = {}

                guard = (
                    dict(guard)
                    if isinstance(
                        guard,
                        Mapping,
                    )
                    else {}
                )

                domain_supported = (
                    _guard_supports_domain(
                        guard
                    )
                )

                verified = bool(
                    business_name
                    and people
                    and domain_supported
                )

                candidates.append({
                    "website": root,
                    "business_name":
                        business_name,
                    "matching_people":
                        people,
                    "domain_supported":
                        domain_supported,
                    "verified":
                        verified,
                    "guard": guard,
                })

            verified_candidates = [
                row
                for row in candidates
                if row.get("verified") is True
            ]

            if len(verified_candidates) == 1:
                winner = verified_candidates[0]

                decision = (
                    "BUSINESS_IDENTITY_VERIFIED"
                )
                next_action = (
                    "resolve_first_party_identity"
                )

                supports.extend([
                    "search_fabric_business_discovery",
                    "source_person_first_party_site_match",
                    "first_party_business_name_observed",
                    "business_domain_supported_by_identity_guard",
                ])

                website = _clean(
                    winner.get("website")
                )

                if website:
                    evidence_refs.append(
                        website
                    )

                for person in (
                    winner.get(
                        "matching_people"
                    )
                    or ()
                ):
                    url = _clean(
                        person.get("url")
                    )
                    if url:
                        evidence_refs.append(
                            url
                        )

                output = {
                    "source_handle": handle,
                    "discovery_query_plan":
                        query_plan,
                    "source_person_names":
                        person_names,
                    "business_identity_verified":
                        True,
                    "business_name":
                        winner["business_name"],
                    "website": website,
                    "first_party_site_verified":
                        True,
                    "matching_people":
                        winner.get(
                            "matching_people"
                        )
                        or [],
                    "candidate_count":
                        len(candidates),
                    "candidates":
                        candidates,
                }

            elif len(verified_candidates) > 1:
                decision = "NEEDS_REVIEW"
                next_action = (
                    "review_conflicting_business_identity"
                )
                blockers.append(
                    "multiple_verified_business_identity_candidates"
                )

                output = {
                    "source_handle": handle,
                    "discovery_query_plan":
                        query_plan,
                    "source_person_names":
                        person_names,
                    "business_identity_verified":
                        False,
                    "business_name": None,
                    "website": None,
                    "first_party_site_verified":
                        False,
                    "candidate_count":
                        len(candidates),
                    "candidates":
                        candidates,
                }

            else:
                decision = (
                    "BUSINESS_IDENTITY_UNRESOLVED"
                )
                next_action = (
                    "hold_for_business_identity_evidence"
                )

                if (
                    discovery_provider_degraded
                    and not discovery_success_observed
                ):
                    decision = (
                        "DISCOVERY_PROVIDER_DEGRADED"
                    )
                    recommended_next_action = (
                        "retry_business_identity_discovery"
                    )
                    blockers.append(
                        "business_identity_search_provider_degraded"
                    )
                elif not candidate_roots:
                    blockers.append(
                        "no_non_social_business_domain_discovered"
                    )
                else:
                    blockers.append(
                        "business_identity_quorum_not_met"
                    )

                output = {
                    "source_handle": handle,
                    "discovery_query_plan":
                        query_plan,
                    "source_person_names":
                        person_names,
                    "business_identity_verified":
                        False,
                    "business_name": None,
                    "website": None,
                    "first_party_site_verified":
                        False,
                    "candidate_count":
                        len(candidates),
                    "candidates":
                        candidates,
                }

    envelope = build_actor_envelope(
        descriptor=DESCRIPTOR,
        actor_input=dict(payload),
        decision=decision,
        recommended_next_action=
            next_action,
        output=output,
        evidence_refs=list(
            dict.fromkeys(
                evidence_refs
            )
        ),
        truth_class="mixed",
        confidence={
            "business_identity":
                0.95
                if output.get(
                    "business_identity_verified"
                )
                else 0.0,
        },
        blockers=blockers,
        supports=supports,
        execution_authority="none",
    )

    return validate_actor_envelope(
        envelope
    )
