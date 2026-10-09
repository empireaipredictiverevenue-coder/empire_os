from __future__ import annotations

from dataclasses import asdict, dataclass, field
from difflib import SequenceMatcher
from hashlib import sha256
from typing import Any
from urllib.parse import urlparse
import re


EMAIL_RE = re.compile(
    r"\b[A-Z0-9._%+-]+@"
    r"[A-Z0-9.-]+\.[A-Z]{2,}\b",
    re.I,
)

PHONE_RE = re.compile(
    r"(?<!\d)"
    r"(?:\+?1[\s.\-()]*)?"
    r"(?:\(?\d{3}\)?[\s.\-()]*)"
    r"\d{3}[\s.\-]*\d{4}"
    r"(?!\d)"
)


@dataclass
class IdentitySignals:
    domain: str

    raw_variants: set[str] = field(
        default_factory=set
    )

    redirects: set[str] = field(
        default_factory=set
    )

    emails: set[str] = field(
        default_factory=set
    )

    phones: set[str] = field(
        default_factory=set
    )

    source_ids: set[str] = field(
        default_factory=set
    )

    evidence: list[str] = field(
        default_factory=list
    )

    direct_site_successes: int = 0
    actively_verified: bool = False


@dataclass(frozen=True)
class PairDecision:
    left: str
    right: str
    decision: str
    confidence: float
    reasons: tuple[str, ...]
    merge_allowed: bool

    def as_dict(self):
        return asdict(self)


def normalize_domain(
    value: str,
) -> str:

    value = (
        value or ""
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


def normalized_phone(
    value: str,
) -> str:

    digits = re.sub(
        r"\D",
        "",
        value or "",
    )

    if (
        len(digits) == 11
        and digits.startswith("1")
    ):
        digits = digits[1:]

    return digits


def extract_emails(
    text: str,
) -> set[str]:

    return {
        match.group(0).lower()
        for match
        in EMAIL_RE.finditer(
            text or ""
        )
    }


def extract_phones(
    text: str,
) -> set[str]:

    result = set()

    for match in PHONE_RE.finditer(
        text or ""
    ):

        phone = normalized_phone(
            match.group(0)
        )

        if len(phone) >= 10:
            result.add(phone)

    return result


def redirect_domain(
    url: str,
) -> str:

    try:
        return normalize_domain(
            urlparse(
                url
            ).hostname
            or ""
        )

    except Exception:
        return ""


def similarity(
    left: str,
    right: str,
) -> float:

    left = normalize_domain(left)
    right = normalize_domain(right)

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


def pair_key(
    left: str,
    right: str,
) -> tuple[str, str]:

    left = normalize_domain(left)
    right = normalize_domain(right)

    return tuple(
        sorted(
            (
                left,
                right,
            )
        )
    )


def override_sets(
    overrides: dict[str, Any],
):

    do_not_merge = {
        pair_key(
            item["left"],
            item["right"],
        )

        for item
        in overrides.get(
            "do_not_merge",
            [],
        )

        if (
            item.get("left")
            and item.get("right")
        )
    }

    same = {}

    for item in overrides.get(
        "same_identity",
        [],
    ):

        left = normalize_domain(
            item.get("left", "")
        )

        right = normalize_domain(
            item.get("right", "")
        )

        if (
            not left
            or not right
        ):
            continue

        same[
            pair_key(
                left,
                right,
            )
        ] = normalize_domain(
            item.get(
                "canonical",
                "",
            )
        ) or None

    return (
        do_not_merge,
        same,
    )


def resolve_pair(
    left: IdentitySignals,
    right: IdentitySignals,
    *,
    overrides: dict[str, Any] | None = None,
) -> PairDecision:

    overrides = overrides or {}

    key = pair_key(
        left.domain,
        right.domain,
    )

    do_not_merge, explicit_same = (
        override_sets(
            overrides
        )
    )

    if key in do_not_merge:

        return PairDecision(
            left=
                key[0],

            right=
                key[1],

            decision=
                "DIFFERENT",

            confidence=
                1.0,

            reasons=(
                "explicit_do_not_merge",
            ),

            merge_allowed=
                False,
        )

    if key in explicit_same:

        return PairDecision(
            left=
                key[0],

            right=
                key[1],

            decision=
                "SAME",

            confidence=
                1.0,

            reasons=(
                "explicit_same_identity",
            ),

            merge_allowed=
                True,
        )

    left_domain = normalize_domain(
        left.domain
    )

    right_domain = normalize_domain(
        right.domain
    )

    if left_domain == right_domain:

        return PairDecision(
            left=
                left_domain,

            right=
                right_domain,

            decision=
                "SAME",

            confidence=
                1.0,

            reasons=(
                "exact_canonical_domain",
            ),

            merge_allowed=
                True,
        )

    fuzzy = similarity(
        left_domain,
        right_domain,
    )

    shared_emails = (
        left.emails
        & right.emails
    )

    shared_phones = (
        left.phones
        & right.phones
    )

    redirect_link = (
        right_domain
        in left.redirects
        or left_domain
        in right.redirects
    )

    reasons = []

    if shared_emails:
        reasons.append(
            "shared_email"
        )

    if shared_phones:
        reasons.append(
            "shared_phone"
        )

    if redirect_link:
        reasons.append(
            "cross_domain_redirect"
        )

    if fuzzy >= 0.90:
        reasons.append(
            "high_name_similarity"
        )

    # Strong, evidence-backed identity merge.
    #
    # Fuzzy matching NEVER satisfies this by itself.
    strong_count = sum(
        (
            bool(
                shared_emails
            ),
            bool(
                shared_phones
            ),
            bool(
                redirect_link
            ),
        )
    )

    if strong_count >= 2:

        return PairDecision(
            left=
                key[0],

            right=
                key[1],

            decision=
                "SAME",

            confidence=
                0.99,

            reasons=
                tuple(
                    reasons
                ),

            merge_allowed=
                True,
        )

    if (
        redirect_link
        and fuzzy >= 0.80
    ):

        return PairDecision(
            left=
                key[0],

            right=
                key[1],

            decision=
                "SAME",

            confidence=
                0.97,

            reasons=
                tuple(
                    reasons
                ),

            merge_allowed=
                True,
        )

    if (
        shared_emails
        and fuzzy >= 0.80
    ):

        return PairDecision(
            left=
                key[0],

            right=
                key[1],

            decision=
                "SAME",

            confidence=
                0.96,

            reasons=
                tuple(
                    reasons
                ),

            merge_allowed=
                True,
        )

    if (
        shared_phones
        and fuzzy >= 0.90
    ):

        return PairDecision(
            left=
                key[0],

            right=
                key[1],

            decision=
                "SAME",

            confidence=
                0.95,

            reasons=
                tuple(
                    reasons
                ),

            merge_allowed=
                True,
        )

    if (
        fuzzy >= 0.90
        or redirect_link
        or shared_emails
        or shared_phones
    ):

        return PairDecision(
            left=
                key[0],

            right=
                key[1],

            decision=
                "UNCERTAIN",

            confidence=
                round(
                    max(
                        fuzzy,
                        0.70,
                    ),
                    4,
                ),

            reasons=
                tuple(
                    reasons
                    or [
                        "possible_relationship"
                    ]
                ),

            merge_allowed=
                False,
        )

    return PairDecision(
        left=
            key[0],

        right=
            key[1],

        decision=
            "DIFFERENT",

        confidence=
            round(
                max(
                    0.60,
                    1.0 - fuzzy,
                ),
                4,
            ),

        reasons=(
            "insufficient_identity_overlap",
        ),

        merge_allowed=
            False,
    )


class UnionFind:

    def __init__(
        self,
        members: list[str],
    ):

        self.parent = {
            item: item
            for item
            in members
        }

    def find(
        self,
        item: str,
    ) -> str:

        parent = self.parent[
            item
        ]

        if parent != item:

            self.parent[
                item
            ] = self.find(
                parent
            )

        return self.parent[
            item
        ]

    def union(
        self,
        left: str,
        right: str,
    ) -> None:

        a = self.find(left)
        b = self.find(right)

        if a == b:
            return

        if a < b:
            self.parent[b] = a

        else:
            self.parent[a] = b


def canonical_score(
    signal: IdentitySignals,
) -> tuple[int, int, int, int, str]:

    return (
        1 if signal.actively_verified else 0,
        int(
            signal.direct_site_successes
        ),
        len(
            signal.source_ids
        ),
        -len(
            signal.domain
        ),
        signal.domain,
    )


def resolve_clusters(
    signals: dict[str, IdentitySignals],
    decisions: list[PairDecision],
    *,
    overrides: dict[str, Any] | None = None,
):

    overrides = overrides or {}

    domains = sorted(
        signals
    )

    uf = UnionFind(
        domains
    )

    blocked, explicit_same = (
        override_sets(
            overrides
        )
    )

    for decision in decisions:

        key = pair_key(
            decision.left,
            decision.right,
        )

        if key in blocked:
            continue

        if (
            decision.decision
            == "SAME"
            and decision.merge_allowed
        ):
            uf.union(
                decision.left,
                decision.right,
            )

    groups: dict[
        str,
        list[str],
    ] = {}

    for domain in domains:

        root = uf.find(
            domain
        )

        groups.setdefault(
            root,
            [],
        ).append(
            domain
        )

    clusters = []
    alias_map = {}

    for members in groups.values():

        explicit_canonicals = []

        member_set = set(
            members
        )

        for (
            left,
            right,
        ), canonical in explicit_same.items():

            if (
                left in member_set
                and right in member_set
                and canonical
                and canonical
                in member_set
            ):
                explicit_canonicals.append(
                    canonical
                )

        if explicit_canonicals:

            canonical = sorted(
                explicit_canonicals
            )[0]

        else:

            canonical = max(
                members,
                key=lambda domain:
                    canonical_score(
                        signals[
                            domain
                        ]
                    ),
            )

        aliases = sorted(
            domain
            for domain
            in members
            if domain != canonical
        )

        for alias in aliases:
            alias_map[
                alias
            ] = canonical

        cluster_raw = "|".join(
            sorted(
                members
            )
        )

        cluster_id = sha256(
            cluster_raw.encode(
                "utf-8"
            )
        ).hexdigest()[:20]

        clusters.append(
            {
                "cluster_id":
                    cluster_id,

                "canonical":
                    canonical,

                "members":
                    sorted(
                        members
                    ),

                "aliases":
                    aliases,

                "duplicate_count":
                    len(
                        aliases
                    ),
            }
        )

    clusters.sort(
        key=lambda item:
            item[
                "canonical"
            ]
    )

    return (
        clusters,
        alias_map,
    )
