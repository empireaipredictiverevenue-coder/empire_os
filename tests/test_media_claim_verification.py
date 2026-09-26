from datetime import datetime, timezone
import json

from empire_os.media_claim_verification import (
    materialize_verified_pack,
    observe_research_sources,
    propose_claims,
    refresh_media_claim_verification,
    verify_claims,
)


def pack():
    return {
        "research_id": "research:1",
        "topic": "Automation Ops",
        "thesis": "Verify what observed sources actually support.",
        "audience": "founders and operators",
        "opportunity_class": "community_pain",
        "sources": [
            {
                "source_ref": "source:1",
                "source_type": "public_search_result",
                "observed_at": "2026-09-23T14:00:00+00:00",
                "lineage_ref": "https://example.test/article",
                "rights_state": "RESEARCH_REFERENCE_ONLY",
            }
        ],
        "claims": [],
        "uncertainty": [
            "Demand and revenue remain unknown.",
        ],
        "claim_verification_required": True,
        "script_ready": False,
        "execution_authority": "none",
    }





def fake_resolver(host, port, **kwargs):
    return [
        (
            2,
            1,
            6,
            "",
            ("93.184.216.34", port),
        )
    ]


def fake_probe(url, **kwargs):
    assert url == "https://example.test/article"
    assert kwargs["max_pages"] == 1
    return {
        "ok": True,
        "final_url": url,
        "pages_checked": [
            {
                "url": url,
                "visible_text": (
                    "Automation can reduce repetitive manual work when "
                    "the workflow is well defined. Results vary by process."
                ),
            }
        ],
    }


class FakeGateway:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def structured_chat(self, messages, **kwargs):
        self.calls.append({
            "messages": messages,
            "kwargs": kwargs,
        })
        return self.responses.pop(0)


def test_direct_source_observation_reuses_search_fabric_probe():
    result = observe_research_sources(
        pack(),
        probe=fake_probe,
        max_sources=3,
        resolver=fake_resolver,
    )

    assert result["observed_source_count"] == 1
    assert result["external_write_performed"] is False
    row = result["observations"][0]
    assert row["source_ref"] == "source:1"
    assert row["direct_source_observed"] is True
    assert row["visible_text_sha256"]


def test_claim_proposal_requires_literal_quote_from_observed_source():
    observations = observe_research_sources(
        pack(),
        probe=fake_probe,
        resolver=fake_resolver,
    )
    gateway = FakeGateway([
        {
            "claims": [
                {
                    "claim_id": "claim:good",
                    "text": (
                        "Automation can reduce repetitive manual work "
                        "when the workflow is well defined."
                    ),
                    "evidence_refs": ["source:1"],
                    "support_source_ref": "source:1",
                    "support_quote": (
                        "Automation can reduce repetitive manual work "
                        "when the workflow is well defined."
                    ),
                    "freshness_class": "CURRENT",
                },
                {
                    "claim_id": "claim:bad",
                    "text": "Automation guarantees revenue growth.",
                    "evidence_refs": ["source:1"],
                    "support_source_ref": "source:1",
                    "support_quote": "Revenue always doubles.",
                    "freshness_class": "CURRENT",
                },
            ]
        }
    ])

    result = propose_claims(
        pack(),
        observations,
        gateway=gateway,
    )

    assert result["proposal_count"] == 1
    assert result["claims"][0]["claim_id"] == "claim:good"
    assert (
        result["claims"][0]["support_quote_machine_matched"]
        is True
    )
    assert result["rejected"][0]["claim_id"] == "claim:bad"
    assert "support_quote_not_found_in_source_text" in (
        result["rejected"][0]["problems"]
    )


def test_second_pass_verification_is_required_for_supported_claim():
    proposals = [
        {
            "claim_id": "claim:1",
            "text": "A narrow factual claim.",
            "evidence_refs": ["source:1"],
            "support_source_ref": "source:1",
            "support_quote": "A narrow factual claim.",
            "freshness_class": "CURRENT",
        }
    ]
    gateway = FakeGateway([
        {
            "reviews": [
                {
                    "claim_id": "claim:1",
                    "verdict": "SUPPORTED",
                    "confidence": 0.93,
                    "reason": "The quote directly entails the claim.",
                }
            ]
        }
    ])

    result = verify_claims(
        proposals,
        gateway=gateway,
    )

    assert result["supported_count"] == 1
    assert result["reviews"][0]["verdict"] == "SUPPORTED"

    low_confidence = FakeGateway([
        {
            "reviews": [
                {
                    "claim_id": "claim:1",
                    "verdict": "SUPPORTED",
                    "confidence": 0.62,
                    "reason": "Weak support.",
                }
            ]
        }
    ])
    result = verify_claims(
        proposals,
        gateway=low_confidence,
    )
    assert result["supported_count"] == 0
    assert result["reviews"][0]["verdict"] == "UNKNOWN"


def test_materialized_verified_pack_is_script_ready_only_with_supported_claim():
    observations = {
        "observations": [
            {
                "source_ref": "source:1",
                "observed_at": "2026-09-23T14:00:00+00:00",
                "visible_text": "Evidence text.",
            }
        ]
    }
    proposals = [
        {
            "claim_id": "claim:1",
            "text": "Evidence text.",
            "evidence_refs": ["source:1"],
            "support_source_ref": "source:1",
            "support_quote": "Evidence text.",
            "freshness_class": "CURRENT",
            "uncertainty": None,
        }
    ]
    reviews = [
        {
            "claim_id": "claim:1",
            "verdict": "SUPPORTED",
            "confidence": 0.95,
            "reason": "Directly supported.",
        }
    ]

    result = materialize_verified_pack(
        pack(),
        proposals=proposals,
        reviews=reviews,
        source_observations=observations,
        now=datetime(2026, 9, 23, 14, 5, tzinfo=timezone.utc),
    )

    assert result["verified_claim_count"] == 1
    assert result["script_ready"] is True
    assert result["claim_verification_required"] is False
    assert result["claims"][0]["verification"]["verdict"] == "SUPPORTED"
    assert result["public_publish_authorized"] is False
    assert result["execution_authority"] == "none"


def test_refresh_claim_verification_is_bounded_and_idempotent(tmp_path):
    source = (
        tmp_path
        / "runtime/media_os/input/research_pack_candidates.json"
    )
    source.parent.mkdir(parents=True)
    source.write_text(json.dumps({
        "candidates": [pack()]
    }))

    gateway = FakeGateway([
        {
            "claims": [
                {
                    "claim_id": "claim:1",
                    "text": (
                        "Automation can reduce repetitive manual work "
                        "when the workflow is well defined."
                    ),
                    "evidence_refs": ["source:1"],
                    "support_source_ref": "source:1",
                    "support_quote": (
                        "Automation can reduce repetitive manual work "
                        "when the workflow is well defined."
                    ),
                    "freshness_class": "CURRENT",
                }
            ]
        },
        {
            "reviews": [
                {
                    "claim_id": "claim:1",
                    "verdict": "SUPPORTED",
                    "confidence": 0.94,
                    "reason": "Direct support.",
                }
            ]
        },
    ])

    first = refresh_media_claim_verification(
        tmp_path,
        gateway=gateway,
        probe=fake_probe,
        max_packs=1,
        max_sources_per_pack=1,
        resolver=fake_resolver,
    )

    assert first["processed_pack_count"] == 1
    assert first["verified_claim_count"] == 1
    assert first["script_ready_count"] == 1
    assert first["external_write_performed"] is False
    assert first["execution_authority"] == "none"

    verified = (
        tmp_path
        / "runtime/media_os/input/verified_research_packs.json"
    )
    assert verified.exists()

    second = refresh_media_claim_verification(
        tmp_path,
        gateway=FakeGateway([]),
        probe=fake_probe,
        max_packs=1,
        max_sources_per_pack=1,
    )
    assert second["skipped_unchanged"] is True


def test_source_observation_blocks_private_and_local_urls():
    private = pack()
    private["sources"][0]["lineage_ref"] = "http://127.0.0.1/admin"

    result = observe_research_sources(
        private,
        probe=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("probe must not be called")
        ),
        resolver=fake_resolver,
    )

    assert result["observed_source_count"] == 0
    assert result["failure_count"] == 1
    assert (
        result["failures"][0]["reason"]
        == "nonpublic_ip_not_allowed"
    )

    rebinding = pack()
    rebinding["sources"][0]["lineage_ref"] = "https://public.example/"

    def private_resolver(host, port, **kwargs):
        return [
            (
                2,
                1,
                6,
                "",
                ("10.0.0.8", port),
            )
        ]

    result = observe_research_sources(
        rebinding,
        probe=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("probe must not be called")
        ),
        resolver=private_resolver,
    )

    assert result["observed_source_count"] == 0
    assert (
        result["failures"][0]["reason"]
        == "dns_resolved_nonpublic_ip"
    )
