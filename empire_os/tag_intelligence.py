"""Unified Search + Revenue Tag Intelligence.

OBSERVE-only analysis for page metadata/social/schema tags and marketing/
measurement tags. The engine reports deterministic repair priority; it never
invents traffic, conversions, revenue loss, compliance status or platform
delivery outcomes.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence


SEVERITY_WEIGHT = {
    "critical": 25,
    "high": 15,
    "medium": 8,
    "low": 3,
    "info": 0,
}


@dataclass(frozen=True)
class TagIssue:
    code: str
    surface: str
    severity: str
    evidence: str
    recommended_action: str
    manual_review_required: bool = False
    execution_allowed: bool = False
    estimated_revenue_loss_cents: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TagIntelligenceReview:
    page_url: str | None
    issues: tuple[TagIssue, ...]
    repair_priority_score: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    info_count: int
    search_tag_issue_count: int
    measurement_tag_issue_count: int
    actual_revenue_impact_known: bool = False
    estimated_revenue_loss_cents: int | None = None
    compliance_status: str = "UNKNOWN"
    mode: str = "OBSERVE"
    execution_authority: str = "none"
    automatic_tag_mutation: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "issues": [issue.as_dict() for issue in self.issues],
        }


def _values(value: Any) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return ()
    return tuple(
        str(item).strip()
        for item in value
        if str(item).strip()
    )


def _issue(
    issues: list[TagIssue],
    code: str,
    surface: str,
    severity: str,
    evidence: str,
    action: str,
    *,
    manual_review: bool = False,
) -> None:
    issues.append(
        TagIssue(
            code=code,
            surface=surface,
            severity=severity,
            evidence=evidence,
            recommended_action=action,
            manual_review_required=manual_review,
        )
    )


def _page_tag_issues(
    page: Mapping[str, Any],
    expectations: Mapping[str, Any],
) -> list[TagIssue]:
    issues: list[TagIssue] = []
    intended_public = expectations.get("intended_public") is True

    title = str(page.get("title") or "").strip()
    if not title:
        _issue(
            issues, "missing_title", "search", "high",
            "No observed <title> value.",
            "Add a unique, useful page title aligned to visible content.",
        )
    if int(page.get("title_count") or (1 if title else 0)) > 1:
        _issue(
            issues, "duplicate_title_elements", "search", "high",
            "Multiple title elements were observed.",
            "Keep one valid title element in the document head.",
        )

    description = str(page.get("meta_description") or "").strip()
    if not description:
        _issue(
            issues, "missing_meta_description", "search", "medium",
            "No observed meta description.",
            "Add a unique page-specific description; do not keyword-stuff it.",
        )

    canonical = str(page.get("canonical_url") or "").strip()
    if not canonical:
        _issue(
            issues, "missing_canonical", "search", "high",
            "No observed canonical URL.",
            "Review and add an evidence-backed canonical URL.",
        )

    robots = str(page.get("robots") or "").lower()
    googlebot = str(page.get("googlebot") or "").lower()
    x_robots = str(page.get("x_robots_tag") or "").lower()
    if intended_public and (
        "noindex" in robots
        or "noindex" in googlebot
        or "noindex" in x_robots
    ):
        _issue(
            issues, "public_page_noindex", "search", "critical",
            "A page expected to be public has a noindex directive.",
            "Review robots/meta and X-Robots-Tag before changing production.",
            manual_review=True,
        )

    og = page.get("open_graph")
    og = dict(og) if isinstance(og, Mapping) else {}
    for key in ("title", "description", "url"):
        if not str(og.get(key) or "").strip():
            _issue(
                issues, f"missing_og_{key}", "social", "medium",
                f"Open Graph {key} was not observed.",
                f"Add og:{key} using verified page content.",
            )
    if not str(og.get("image") or "").strip():
        _issue(
            issues, "missing_og_image", "social", "low",
            "No Open Graph image was observed.",
            "Add a suitable social preview image.",
        )

    twitter = page.get("twitter")
    twitter = dict(twitter) if isinstance(twitter, Mapping) else {}
    if not str(twitter.get("card") or "").strip():
        _issue(
            issues, "missing_twitter_card", "social", "low",
            "No X/Twitter card metadata was observed.",
            "Add a card type and verified social preview metadata.",
        )

    if expectations.get("site_verification_expected") is True:
        verification = page.get("site_verification_tags")
        verification = (
            dict(verification)
            if isinstance(verification, Mapping)
            else {}
        )
        if not any(
            str(value or "").strip()
            for value in verification.values()
        ):
            _issue(
                issues, "site_verification_tag_missing", "technical", "medium",
                "Site verification metadata was expected but no supported verification tag was observed.",
                "Verify the intended search/social webmaster verification method.",
                manual_review=True,
            )

    if expectations.get("schema_expected") is True:
        if not _values(page.get("json_ld_types")):
            _issue(
                issues, "structured_data_missing", "schema", "medium",
                "Structured data was expected but no JSON-LD type was observed.",
                "Generate a visible-content-only schema preview and validate it.",
                manual_review=True,
            )

    if expectations.get("hreflang_expected") is True:
        if not _values(page.get("hreflang")):
            _issue(
                issues, "hreflang_missing", "search", "medium",
                "International targeting was expected but hreflang was absent.",
                "Review language/region alternates and reciprocal references.",
                manual_review=True,
            )

    if page.get("viewport_present") is False:
        _issue(
            issues, "viewport_missing", "technical", "medium",
            "Viewport metadata was explicitly observed as missing.",
            "Add an appropriate viewport declaration.",
        )
    if page.get("charset_present") is False:
        _issue(
            issues, "charset_missing", "technical", "low",
            "Character-set metadata was explicitly observed as missing.",
            "Declare a valid charset early in the document head.",
        )

    h1_count = page.get("h1_count")
    if h1_count is not None:
        count = int(h1_count)
        if count == 0:
            _issue(
                issues, "h1_missing", "content", "high",
                "No H1 was observed.",
                "Add a useful primary heading aligned to visible page intent.",
            )
        elif count > 1:
            _issue(
                issues, "multiple_h1", "content", "medium",
                f"{count} H1 elements were observed.",
                "Review heading hierarchy for clarity and accessibility.",
            )

    missing_alt = page.get("images_missing_alt")
    if missing_alt is not None and int(missing_alt) > 0:
        _issue(
            issues, "image_alt_missing", "content", "medium",
            f"{int(missing_alt)} images were observed without alt text.",
            "Add useful alt text where images convey meaningful information.",
        )

    if page.get("meta_keywords_present") is True:
        _issue(
            issues, "meta_keywords_ignored", "search", "info",
            "A meta keywords tag was observed.",
            "Do not optimise this tag for Google Search; focus on visible content.",
        )

    return issues


def _measurement_tag_issues(
    tags: Mapping[str, Any],
    expectations: Mapping[str, Any],
) -> list[TagIssue]:
    issues: list[TagIssue] = []

    google_tags = _values(tags.get("google_tag_ids"))
    ga4_ids = _values(tags.get("ga4_measurement_ids"))
    ads_ids = _values(tags.get("google_ads_conversion_ids"))
    gtm_ids = _values(tags.get("gtm_container_ids"))
    pixel_ids = _values(tags.get("meta_pixel_ids"))

    google_expected = (
        expectations.get("google_analytics_expected") is True
        or expectations.get("google_ads_expected") is True
    )
    if google_expected and not google_tags and not gtm_ids:
        _issue(
            issues, "google_tag_missing", "measurement", "high",
            "Google measurement was expected but no Google tag/GTM container was observed.",
            "Install or restore the governed Google tag/Tag Manager implementation.",
            manual_review=True,
        )

    if expectations.get("google_analytics_expected") is True and not ga4_ids:
        _issue(
            issues, "ga4_measurement_missing", "measurement", "high",
            "GA4 measurement was expected but no measurement ID was observed.",
            "Verify GA4 configuration and the intended data stream.",
            manual_review=True,
        )

    if expectations.get("google_ads_expected") is True and not ads_ids:
        _issue(
            issues, "google_ads_conversion_tag_missing", "measurement", "high",
            "Google Ads conversion measurement was expected but no conversion ID was observed.",
            "Review Ads conversion tracking before campaign optimisation.",
            manual_review=True,
        )

    duplicates = tags.get("duplicate_tag_counts")
    duplicates = dict(duplicates) if isinstance(duplicates, Mapping) else {}
    for name, count in sorted(duplicates.items()):
        if int(count or 0) > 1:
            _issue(
                issues, "duplicate_measurement_tag", "measurement", "high",
                f"{name} was observed {int(count)} times.",
                "Remove unintended duplicate firing and re-test events.",
                manual_review=True,
            )

    meta_expected = expectations.get("meta_ads_expected") is True
    if meta_expected and not pixel_ids:
        _issue(
            issues, "meta_pixel_missing", "measurement", "high",
            "Meta Ads measurement was expected but no Pixel ID was observed.",
            "Verify the intended Meta Pixel implementation.",
            manual_review=True,
        )

    capi = tags.get("meta_capi_enabled")
    if meta_expected and pixel_ids and capi is False:
        _issue(
            issues, "meta_capi_not_enabled", "measurement", "medium",
            "Meta Pixel was observed while Conversions API was explicitly disabled.",
            "Review whether server-side event delivery is appropriate for this account.",
            manual_review=True,
        )
    elif meta_expected and pixel_ids and capi is None:
        _issue(
            issues, "meta_capi_status_unverified", "measurement", "medium",
            "Meta Pixel was observed but server-side Conversions API delivery was not verified.",
            "Verify server-side event delivery in the connected Meta evidence source.",
            manual_review=True,
        )

    if pixel_ids and capi is True:
        dedup = tags.get("meta_event_id_dedup")
        if dedup is not True:
            _issue(
                issues, "meta_pixel_capi_dedup_unverified", "measurement", "critical",
                "Browser and server Meta events are enabled but event-ID deduplication is not verified.",
                "Verify browser/server event_id parity before trusting conversion counts.",
                manual_review=True,
            )

    required_events = set(_values(expectations.get("required_events")))
    observed_events = set(_values(tags.get("observed_events")))
    for event in sorted(required_events - observed_events):
        _issue(
            issues, "required_conversion_event_missing", "conversion", "high",
            f"Required event '{event}' was not observed.",
            "Verify trigger conditions, event naming and destination delivery.",
            manual_review=True,
        )

    event_dupes = tags.get("duplicate_event_counts")
    event_dupes = dict(event_dupes) if isinstance(event_dupes, Mapping) else {}
    for event, count in sorted(event_dupes.items()):
        if int(count or 0) > 1:
            _issue(
                issues, "duplicate_conversion_event", "conversion", "high",
                f"Event '{event}' was declared {int(count)} times in the supplied measurement evidence.",
                "Inspect triggers/data layer and verify whether duplicate delivery actually occurs.",
                manual_review=True,
            )

    channel_checks = (
        (
            "linkedin_ads_expected",
            "linkedin_insight_partner_ids",
            "linkedin_insight_tag_missing",
            "LinkedIn Insight Tag",
        ),
        (
            "tiktok_ads_expected",
            "tiktok_pixel_ids",
            "tiktok_pixel_missing",
            "TikTok Pixel",
        ),
        (
            "reddit_ads_expected",
            "reddit_pixel_ids",
            "reddit_pixel_missing",
            "Reddit Pixel",
        ),
        (
            "pinterest_ads_expected",
            "pinterest_tag_ids",
            "pinterest_tag_missing",
            "Pinterest Tag",
        ),
    )
    for expectation_key, tag_key, code, label in channel_checks:
        if (
            expectations.get(expectation_key) is True
            and not _values(tags.get(tag_key))
        ):
            _issue(
                issues, code, "measurement", "high",
                f"{label} was expected but no identifier was observed.",
                f"Verify the governed {label} implementation.",
                manual_review=True,
            )

    if (
        expectations.get("microsoft_ads_expected") is True
        and tags.get("microsoft_uet_present") is not True
    ):
        _issue(
            issues, "microsoft_uet_missing", "measurement", "high",
            "Microsoft Ads UET was expected but was not observed.",
            "Verify the governed Microsoft UET implementation.",
            manual_review=True,
        )

    if expectations.get("consent_review_required") is True:
        consent = tags.get("consent_mode_enabled")
        if consent is not True:
            _issue(
                issues, "consent_configuration_unverified", "privacy", "high",
                "Consent review was required but an enabled consent configuration was not verified.",
                "Perform a jurisdiction/account-specific consent and tag-firing review.",
                manual_review=True,
            )

    if expectations.get("server_side_tagging_expected") is True:
        if tags.get("server_side_tagging") is not True:
            _issue(
                issues, "server_side_tagging_unavailable", "measurement", "medium",
                "Server-side tagging was expected but not observed.",
                "Review server-side tagging architecture, cost and data-governance fit.",
                manual_review=True,
            )

    if expectations.get("revenue_attribution_expected") is True:
        if tags.get("revenue_truth_linked") is not True:
            _issue(
                issues, "revenue_truth_link_missing", "attribution", "high",
                "Measurement events are not verified as linked to canonical Revenue Truth.",
                "Join observed conversion identifiers to recognized commercial outcomes.",
                manual_review=True,
            )

    return issues


def review_tag_intelligence(
    *,
    page_tags: Mapping[str, Any] | None = None,
    measurement_tags: Mapping[str, Any] | None = None,
    expectations: Mapping[str, Any] | None = None,
) -> TagIntelligenceReview:
    page = dict(page_tags or {})
    measurement = dict(measurement_tags or {})
    expected = dict(expectations or {})

    issues = [
        *_page_tag_issues(page, expected),
        *_measurement_tag_issues(measurement, expected),
    ]
    issues.sort(
        key=lambda item: (
            -SEVERITY_WEIGHT[item.severity],
            item.surface,
            item.code,
        )
    )

    score = min(
        100,
        sum(SEVERITY_WEIGHT[item.severity] for item in issues),
    )
    counts = {
        severity: sum(item.severity == severity for item in issues)
        for severity in SEVERITY_WEIGHT
    }
    search_surfaces = {"search", "social", "schema", "technical", "content"}

    return TagIntelligenceReview(
        page_url=str(page.get("url") or "").strip() or None,
        issues=tuple(issues),
        repair_priority_score=score,
        critical_count=counts["critical"],
        high_count=counts["high"],
        medium_count=counts["medium"],
        low_count=counts["low"],
        info_count=counts["info"],
        search_tag_issue_count=sum(
            item.surface in search_surfaces for item in issues
        ),
        measurement_tag_issue_count=sum(
            item.surface not in search_surfaces for item in issues
        ),
    )



@dataclass(frozen=True)
class TagChange:
    field: str
    surface: str
    previous: Any
    current: Any
    severity: str
    reason: str
    execution_allowed: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _normalized_snapshot(
    page_tags: Mapping[str, Any] | None,
    measurement_tags: Mapping[str, Any] | None,
) -> dict[str, Any]:
    page = dict(page_tags or {})
    measurement = dict(measurement_tags or {})
    return {
        "title": page.get("title"),
        "meta_description": page.get("meta_description"),
        "canonical_url": page.get("canonical_url"),
        "robots": page.get("robots"),
        "googlebot": page.get("googlebot"),
        "x_robots_tag": page.get("x_robots_tag"),
        "site_verification_tags": dict(
            page.get("site_verification_tags") or {}
        ),
        "open_graph": dict(page.get("open_graph") or {}),
        "twitter": dict(page.get("twitter") or {}),
        "json_ld_types": sorted(_values(page.get("json_ld_types"))),
        "hreflang": sorted(_values(page.get("hreflang"))),
        "google_tag_ids": sorted(_values(measurement.get("google_tag_ids"))),
        "gtm_container_ids": sorted(_values(measurement.get("gtm_container_ids"))),
        "ga4_measurement_ids": sorted(_values(measurement.get("ga4_measurement_ids"))),
        "google_ads_conversion_ids": sorted(
            _values(measurement.get("google_ads_conversion_ids"))
        ),
        "meta_pixel_ids": sorted(_values(measurement.get("meta_pixel_ids"))),
        "linkedin_insight_partner_ids": sorted(
            _values(measurement.get("linkedin_insight_partner_ids"))
        ),
        "tiktok_pixel_ids": sorted(
            _values(measurement.get("tiktok_pixel_ids"))
        ),
        "reddit_pixel_ids": sorted(
            _values(measurement.get("reddit_pixel_ids"))
        ),
        "pinterest_tag_ids": sorted(
            _values(measurement.get("pinterest_tag_ids"))
        ),
        "microsoft_uet_present": measurement.get(
            "microsoft_uet_present"
        ),
        "meta_capi_enabled": measurement.get("meta_capi_enabled"),
        "meta_event_id_dedup": measurement.get("meta_event_id_dedup"),
        "consent_mode_enabled": measurement.get("consent_mode_enabled"),
        "server_side_tagging": measurement.get("server_side_tagging"),
        "observed_events": sorted(_values(measurement.get("observed_events"))),
    }


def compare_tag_snapshots(
    *,
    previous_page_tags: Mapping[str, Any] | None = None,
    current_page_tags: Mapping[str, Any] | None = None,
    previous_measurement_tags: Mapping[str, Any] | None = None,
    current_measurement_tags: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    previous = _normalized_snapshot(
        previous_page_tags,
        previous_measurement_tags,
    )
    current = _normalized_snapshot(
        current_page_tags,
        current_measurement_tags,
    )

    critical_fields = {
        "robots",
        "googlebot",
        "x_robots_tag",
        "canonical_url",
        "meta_pixel_ids",
        "linkedin_insight_partner_ids",
        "tiktok_pixel_ids",
        "reddit_pixel_ids",
        "pinterest_tag_ids",
        "microsoft_uet_present",
        "ga4_measurement_ids",
        "google_ads_conversion_ids",
        "meta_event_id_dedup",
    }
    high_fields = {
        "title",
        "google_tag_ids",
        "gtm_container_ids",
        "observed_events",
        "consent_mode_enabled",
    }
    measurement_fields = {
        "google_tag_ids",
        "gtm_container_ids",
        "ga4_measurement_ids",
        "google_ads_conversion_ids",
        "meta_pixel_ids",
        "linkedin_insight_partner_ids",
        "tiktok_pixel_ids",
        "reddit_pixel_ids",
        "pinterest_tag_ids",
        "microsoft_uet_present",
        "meta_capi_enabled",
        "meta_event_id_dedup",
        "consent_mode_enabled",
        "server_side_tagging",
        "observed_events",
    }

    changes: list[TagChange] = []
    for field in sorted(previous):
        before = previous[field]
        after = current[field]
        if before == after:
            continue

        severity = (
            "critical"
            if field in critical_fields
            else "high"
            if field in high_fields
            else "medium"
        )
        surface = "measurement" if field in measurement_fields else "search"
        reason = "tag_or_configuration_changed"
        if before not in (None, "", [], {}) and after in (None, "", [], {}):
            reason = "previously_observed_tag_missing"
        elif before in (None, "", [], {}) and after not in (None, "", [], {}):
            reason = "new_tag_or_configuration_observed"

        changes.append(
            TagChange(
                field=field,
                surface=surface,
                previous=before,
                current=after,
                severity=severity,
                reason=reason,
            )
        )

    return {
        "schema_version": "empire.tag_change_monitor.v1",
        "mode": "OBSERVE",
        "change_count": len(changes),
        "critical_change_count": sum(
            item.severity == "critical" for item in changes
        ),
        "high_change_count": sum(
            item.severity == "high" for item in changes
        ),
        "changes": [item.as_dict() for item in changes],
        "automatic_repair": False,
        "execution_authority": "none",
    }
