from empire_os.canonical_identity_resolution import (
    IdentitySignals,
    resolve_clusters,
    resolve_pair,
    similarity,
)


def signal(
    domain,
    *,
    emails=(),
    phones=(),
    redirects=(),
):

    item = IdentitySignals(
        domain=domain
    )

    item.emails.update(
        emails
    )

    item.phones.update(
        phones
    )

    item.redirects.update(
        redirects
    )

    return item


def test_fuzzy_alone_never_merges():

    left = signal(
        "positioncalls.com"
    )

    right = signal(
        "positoncalls.com"
    )

    decision = resolve_pair(
        left,
        right,
    )

    assert similarity(
        left.domain,
        right.domain,
    ) >= 0.90

    assert decision.decision == (
        "UNCERTAIN"
    )

    assert not decision.merge_allowed


def test_redirect_plus_similarity_can_merge():

    left = signal(
        "oldbrandcalls.com",
        redirects={
            "oldbrandcall.com"
        },
    )

    right = signal(
        "oldbrandcall.com"
    )

    result = resolve_pair(
        left,
        right,
    )

    assert result.decision == "SAME"
    assert result.merge_allowed


def test_two_strong_signals_merge():

    left = signal(
        "brand-a.com",
        emails={
            "partners@company.com"
        },
        phones={
            "2125551212"
        },
    )

    right = signal(
        "brand-b.com",
        emails={
            "partners@company.com"
        },
        phones={
            "2125551212"
        },
    )

    result = resolve_pair(
        left,
        right,
    )

    assert result.decision == "SAME"
    assert result.merge_allowed


def test_do_not_merge_overrides_everything():

    left = signal(
        "brand-a.com",
        emails={
            "partners@company.com"
        },
        phones={
            "2125551212"
        },
    )

    right = signal(
        "brand-b.com",
        emails={
            "partners@company.com"
        },
        phones={
            "2125551212"
        },
    )

    overrides = {
        "do_not_merge": [
            {
                "left":
                    "brand-a.com",

                "right":
                    "brand-b.com",
            }
        ]
    }

    result = resolve_pair(
        left,
        right,
        overrides=overrides,
    )

    assert result.decision == (
        "DIFFERENT"
    )

    assert not result.merge_allowed


def test_cluster_only_merges_confirmed_same():

    signals = {
        "positioncalls.com":
            signal(
                "positioncalls.com"
            ),

        "positoncalls.com":
            signal(
                "positoncalls.com"
            ),

        "brand-a.com":
            signal(
                "brand-a.com",
                emails={
                    "partner@same.com"
                },
                phones={
                    "2125551212"
                },
            ),

        "brand-b.com":
            signal(
                "brand-b.com",
                emails={
                    "partner@same.com"
                },
                phones={
                    "2125551212"
                },
            ),
    }

    decisions = [
        resolve_pair(
            signals[
                "positioncalls.com"
            ],
            signals[
                "positoncalls.com"
            ],
        ),

        resolve_pair(
            signals[
                "brand-a.com"
            ],
            signals[
                "brand-b.com"
            ],
        ),
    ]

    clusters, aliases = (
        resolve_clusters(
            signals,
            decisions,
        )
    )

    assert len(clusters) == 3

    assert (
        "positioncalls.com"
        not in aliases
        or aliases.get(
            "positioncalls.com"
        )
        != "positoncalls.com"
    )
