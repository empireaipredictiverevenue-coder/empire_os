"""Regression tests for Search Fabric identity and enrichment safety."""

from unittest.mock import patch

import empire_os.prospect_enrichment as pe
from empire_os.search_fabric.identity_guard import (
    assess_first_party_identity,
)
from empire_os.search_fabric.site_probe import (
    _valid_email,
    _valid_phone,
)


class TestIdentityFirewall:
    def test_existing_first_party_site_is_accepted(self):
        result = assess_first_party_identity(
            prospect={
                "business_name": "CTD Restoration LLC",
                "metro": "Dallas-Fort Worth",
                "niche": "restoration",
                "website": "https://www.ctdrestoration.com/",
            },
            candidate_url="https://www.ctdrestoration.com/",
            probe={
                "domain": "ctdrestoration.com",
                "title": (
                    "Home Remodeling | Dallas, TX | "
                    "CTD Restoration LLC"
                ),
                "description": (
                    "CTD Restoration LLC provides "
                    "restoration services."
                ),
                "business_names": [
                    "CTD Restoration LLC",
                ],
                "schema_types": [
                    "LocalBusiness",
                ],
            },
        )

        assert result["accepted"] is True
        assert result["existing_first_party_support"] is True

    def test_discovered_real_first_party_domain_is_accepted(self):
        result = assess_first_party_identity(
            prospect={
                "business_name": "Sunhut Solar LLC",
                "metro": "El Paso",
                "niche": "solar",
                "website": "",
            },
            candidate_url="https://sunhutsolar.com/",
            probe={
                "domain": "sunhutsolar.com",
                "title": "Sunhut Solar LLC",
                "description": (
                    "Sunhut Solar LLC provides "
                    "solar installation."
                ),
                "business_names": [
                    "Sunhut Solar LLC",
                ],
                "schema_types": [
                    "LocalBusiness",
                ],
            },
        )

        assert result["accepted"] is True
        assert result["discovery_domain_supported"] is True
        assert "sunhut" in result["distinctive_identity_terms"]

    def test_nextdoor_profile_is_not_canonical_business_site(self):
        result = assess_first_party_identity(
            prospect={
                "business_name": "Sunhut Solar LLC",
                "metro": "El Paso",
                "niche": "solar",
                "website": "",
            },
            candidate_url=(
                "https://nextdoor.com/pages/"
                "sunhut-solar-llc-el-paso-tx/photos"
            ),
            probe={
                "domain": "nextdoor.com",
                "title": (
                    "Sunhut Solar LLC - El Paso, TX - Nextdoor"
                ),
                "description": (
                    "Sunhut Solar LLC in El Paso, TX."
                ),
                "business_names": [
                    "Sunhut Solar LLC",
                ],
                "schema_types": [
                    "LocalBusiness",
                ],
            },
        )

        assert result["accepted"] is False
        assert result["known_third_party_domain"] is True
        assert (
            "candidate_is_known_third_party_platform"
            in result["reasons"]
        )

    def test_listing_page_is_not_canonical_business_site(self):
        result = assess_first_party_identity(
            prospect={
                "business_name": (
                    "A+ffordable Water Mitigation "
                    "& Home Services"
                ),
                "metro": "Houston",
                "niche": "water_mitigation",
                "website": "",
            },
            candidate_url=(
                "https://prismpaintingcompany.com/business/"
                "affordable-water-mitigation-"
                "home-services-tx-154769"
            ),
            probe={
                "domain": "prismpaintingcompany.com",
                "title": (
                    "Find A+ffordable Water Mitigation "
                    "& Home Services in Houston, TX"
                ),
                "description": (
                    "Find contact details and connect "
                    "with local pros today."
                ),
                "business_names": [
                    "A+ffordable Water Mitigation & Home Services",
                    "Prime House Painting",
                    "New Generation Painters",
                    "J&L Painting and Construction",
                    "Grace Painting And Remodeling",
                    "D & J Painting",
                ],
                "schema_types": [
                    "CollectionPage",
                    "ItemList",
                    "LocalBusiness",
                ],
            },
        )

        assert result["accepted"] is False
        assert result["profile_path"] is True
        assert result["discovery_domain_supported"] is False
        assert (
            "discovered_candidate_is_profile_or_listing_page"
            in result["reasons"]
        )

    def test_generic_service_location_is_not_business_identity(self):
        result = assess_first_party_identity(
            prospect={
                "business_name": (
                    "Concrete Contractor in El Paso, TX"
                ),
                "metro": "El Paso",
                "niche": "general_contractor",
                "website": "",
            },
            candidate_url=(
                "https://terranovaconstructiongroup.com/"
            ),
            probe={
                "domain": (
                    "terranovaconstructiongroup.com"
                ),
                "title": (
                    "Terranova Construction Group | "
                    "Licensed General Contractor "
                    "In El Paso, Tx."
                ),
                "description": (
                    "Terranova Construction Group "
                    "specializes in concrete and "
                    "construction projects."
                ),
                "business_names": [
                    "Terranova Construction Group",
                ],
                "schema_types": [
                    "WebSite",
                    "LocalBusiness",
                ],
            },
        )

        assert result["accepted"] is False
        assert result["discovered_generic_identity"] is True
        assert result["distinctive_identity_terms"] == []
        assert (
            "prospect_identity_too_generic_for_discovery"
            in result["reasons"]
        )


class TestContactEvidenceHygiene:
    def test_real_email_is_accepted(self):
        assert _valid_email(
            "ctd@ctdrestoration.com"
        ) is True

    def test_template_email_is_rejected(self):
        assert _valid_email(
            "your@email.com"
        ) is False

    def test_example_domain_email_is_rejected(self):
        assert _valid_email(
            "sales@example.com"
        ) is False

    def test_asset_filename_is_not_email(self):
        assert _valid_email(
            "mood-like-off_16@"
            "3x-1298283633a0f2ffc7d073c5c4b14338.png"
        ) is False

    def test_real_phone_is_accepted(self):
        assert _valid_phone(
            "(817) 269-3500"
        ) is True

    def test_555_template_phone_is_rejected(self):
        assert _valid_phone(
            "+1 555-123-4567"
        ) is False


class TestEnrichmentFailClosed:
    def test_probe_failure_cannot_score_candidate(self):
        candidate = (
            "https://govtribe.com/vendors/"
            "sunhut-llc-11a55"
        )

        discovery = {
            "source": "search_fabric",
            "query": "Sunhut Solar LLC El Paso solar",
            "url": candidate,
            "confidence_score": 0.75,
            "relevance_score": 1.0,
            "geo_score": 0.5,
            "entity_score": 1.0,
            "provenance": [
                "duckduckgo_html",
            ],
        }

        with patch.object(
            pe,
            "_discover_website",
            return_value=(candidate, discovery),
        ), patch.object(
            pe,
            "_extract_site",
            side_effect=RuntimeError(
                "simulated_site_probe_failure"
            ),
        ), patch.object(
            pe,
            "_rdap",
        ) as rdap:
            result = pe.enrich_prospect_for_scoring(
                {
                    "business_name": "Sunhut Solar LLC",
                    "metro": "El Paso",
                    "niche": "solar",
                    "website": "",
                }
            )

        search_ev = next(
            item
            for item in result["evidence"]
            if item.get("source") == "search_fabric"
        )

        website_ev = next(
            item
            for item in result["evidence"]
            if item.get("source") == "website"
        )

        assert result["fields"] == {}
        assert result["sources"] == []
        assert result["enrichment_score"] == 0.0
        assert search_ev["accepted"] is False
        assert website_ev["accepted"] is False
        rdap.assert_not_called()

    def test_rejected_listing_cannot_score_or_call_rdap(self):
        candidate = (
            "https://prismpaintingcompany.com/business/"
            "affordable-water-mitigation-"
            "home-services-tx-154769"
        )

        discovery = {
            "source": "search_fabric",
            "query": (
                "A+ffordable Water Mitigation "
                "& Home Services Houston water_mitigation"
            ),
            "url": candidate,
            "confidence_score": 0.775,
            "relevance_score": 1.0,
            "geo_score": 0.5,
            "entity_score": 1.0,
            "provenance": [
                "duckduckgo_html",
            ],
        }

        site_fields = {
            "website": candidate,
            "site_title": (
                "Find A+ffordable Water Mitigation "
                "& Home Services in Houston, TX"
            ),
            "meta_description": (
                "Find contact details and connect "
                "with local pros today."
            ),
            "phone": "(832) 217-7303",
            "address": "Houston, TX, 77063, US",
        }

        probe = {
            "ok": True,
            "domain": "prismpaintingcompany.com",
            "canonical_url": candidate,
            "title": site_fields["site_title"],
            "description": site_fields["meta_description"],
            "business_names": [
                "A+ffordable Water Mitigation & Home Services",
                "Prime House Painting",
                "New Generation Painters",
                "J&L Painting and Construction",
                "Grace Painting And Remodeling",
                "D & J Painting",
            ],
            "schema_types": [
                "CollectionPage",
                "ItemList",
                "LocalBusiness",
            ],
            "pages_checked": [
                candidate,
            ],
            "evidence_score": 0.7,
        }

        with patch.object(
            pe,
            "_discover_website",
            return_value=(candidate, discovery),
        ), patch.object(
            pe,
            "_extract_site",
            return_value=(site_fields, probe),
        ), patch.object(
            pe,
            "_rdap",
        ) as rdap:
            result = pe.enrich_prospect_for_scoring(
                {
                    "business_name": (
                        "A+ffordable Water Mitigation "
                        "& Home Services"
                    ),
                    "metro": "Houston",
                    "niche": "water_mitigation",
                    "website": "",
                }
            )

        identity = next(
            item
            for item in result["evidence"]
            if item.get("source") == "identity_guard"
        )

        search_ev = next(
            item
            for item in result["evidence"]
            if item.get("source") == "search_fabric"
        )

        assert identity["accepted"] is False
        assert search_ev["accepted"] is False
        assert result["fields"] == {}
        assert result["sources"] == []
        assert result["enrichment_score"] == 0.0
        rdap.assert_not_called()


class TestAcquisitionWebsiteIdentity:
    def test_acquisition_website_precedes_search_fabric(self):
        with patch.object(pe, "fused_search") as fused:
            website, discovery = pe._discover_website(
                {
                    "business_name": "All Star Roofing",
                    "metro": "Austin, TX",
                    "niche": "roofing",
                    "website": "",
                    "_acquisition_website": (
                        "https://allstarroofingtexas.com/"
                    ),
                }
            )

        assert website == "https://allstarroofingtexas.com"
        assert discovery["source"] == "acquisition_evidence"
        assert discovery["provenance"] == ["prospect_acquisitions"]
        fused.assert_not_called()

    def test_phone_mismatch_rejects_same_name_site(self):
        candidate = "https://allstarroofingservice.repair"
        discovery = {
            "source": "search_fabric",
            "url": candidate,
            "confidence_score": 0.9,
            "relevance_score": 1.0,
            "geo_score": 1.0,
            "entity_score": 1.0,
            "provenance": ["duckduckgo_html"],
        }
        site_fields = {
            "website": candidate,
            "email": "info@allstarroofingservice.repair",
            "phone": "255-876-5432",
        }
        probe = {
            "ok": True,
            "domain": "allstarroofingservice.repair",
            "canonical_url": candidate + "/",
            "phones": ["255-876-5432"],
            "pages_checked": [{"url": candidate + "/"}],
            "evidence_score": 0.6,
        }
        accepted_identity = {
            "accepted": True,
            "candidate_url": candidate,
            "reasons": [],
        }

        with patch.object(
            pe, "_discover_website", return_value=(candidate, discovery)
        ), patch.object(
            pe, "_extract_site", return_value=(site_fields, probe)
        ), patch.object(
            pe, "assess_first_party_identity", return_value=accepted_identity
        ), patch.object(pe, "_rdap") as rdap:
            result = pe.enrich_prospect_for_scoring(
                {
                    "business_name": "All Star Roofing",
                    "metro": "Austin, TX",
                    "niche": "roofing",
                    "phone": "+1-512-477-7827",
                    "website": "",
                }
            )

        identity = next(
            item for item in result["evidence"]
            if item.get("source") == "identity_guard"
        )
        search_ev = next(
            item for item in result["evidence"]
            if item.get("source") == "search_fabric"
        )
        assert identity["accepted"] is False
        assert identity["source_phone_match"] is False
        assert "phone_mismatch" in identity["reasons"]
        assert search_ev["accepted"] is False
        assert result["fields"] == {}
        assert result["enrichment_score"] == 0.0
        rdap.assert_not_called()

    def test_matching_source_phone_allows_verified_acquisition_site(self):
        candidate = "https://allstarroofingtexas.com"
        site_fields = {
            "website": candidate,
            "email": "info@allstarroofingtx.com",
            "phone": "512-477-7827",
        }
        probe = {
            "ok": True,
            "domain": "allstarroofingtexas.com",
            "canonical_url": candidate + "/",
            "phones": ["512-477-7827", "512-635-4936"],
            "pages_checked": [{"url": candidate + "/"}],
            "evidence_score": 0.8,
        }
        accepted_identity = {
            "accepted": True,
            "candidate_url": candidate,
            "reasons": [],
        }

        with patch.object(
            pe, "_extract_site", return_value=(site_fields, probe)
        ), patch.object(
            pe, "assess_first_party_identity", return_value=accepted_identity
        ), patch.object(pe, "_rdap", return_value={}):
            result = pe.enrich_prospect_for_scoring(
                {
                    "business_name": "All Star Roofing",
                    "metro": "Austin, TX",
                    "niche": "roofing",
                    "phone": "+1-512-477-7827",
                    "website": "",
                    "_acquisition_website": candidate,
                }
            )

        identity = next(
            item for item in result["evidence"]
            if item.get("source") == "identity_guard"
        )
        acquisition_ev = next(
            item for item in result["evidence"]
            if item.get("source") == "acquisition_evidence"
        )
        assert identity["accepted"] is True
        assert identity["source_phone_match"] is True
        assert acquisition_ev["accepted"] is True
        assert result["fields"]["website"] == candidate
        assert result["fields"]["email"] == "info@allstarroofingtx.com"
