# Tag Intelligence & Revenue Measurement Monitor

Status: **BUILT / OBSERVE-ONLY / UNPRICED MRR PRODUCT**

Product key: `tag_intelligence_monitor`

## Purpose

Monitor the metadata and measurement layer that sits between a business,
search engines, social previews, paid-media platforms and Revenue Truth.

The product does not silently edit client sites or advertising accounts.
It observes, detects regressions, prioritises repairs and preserves unknown
states when platform delivery cannot be verified.

## Search / page tag coverage

- title and duplicate title elements;
- meta description;
- canonical URL;
- robots, googlebot and X-Robots-Tag;
- JSON-LD / structured-data presence;
- hreflang;
- Open Graph;
- X/Twitter cards;
- viewport and charset;
- H1 hierarchy;
- missing image alt attributes;
- Google / Facebook / Bing site-verification meta;
- meta keywords detection as informational only.

## Measurement / revenue tag coverage

Static first-party markup detection currently covers:

- Google tag;
- Google Tag Manager;
- GA4 measurement IDs;
- Google Ads conversion IDs;
- Meta Pixel;
- LinkedIn Insight Tag;
- TikTok Pixel;
- Microsoft Ads UET presence;
- Reddit Pixel;
- Pinterest Tag;
- declared gtag/fbq events;
- duplicate tag declarations;
- duplicate event declarations;
- Google consent-mode code presence.

Connected evidence fields are also reserved for:

- Meta Conversions API state;
- browser/server event-ID dedup verification;
- server-side tagging;
- consent review;
- Revenue Truth linkage.

Static markup is not treated as proof that an event fired or was accepted by
an advertising/analytics platform.

## Continuous monitoring

`empire-tag-intelligence.timer` runs every six hours.

Pipeline:

1. observe configured first-party pages;
2. extract page/search/social tags;
3. extract static measurement-tag signals;
4. apply account/site expectations;
5. generate repair-priority findings;
6. compare with the previous snapshot;
7. surface critical/high regressions in Founder Console and Predictive Cloud.

Default public target: `https://empire-ai.co.uk`.

Client/tenant targets can be supplied through:
`runtime/tag_intelligence/targets.json`.

Reference shape:
`config/tag_intelligence_targets.example.json`.

## Commercial model

Current model: `monthly_subscription`.

Buyer groups:
- local businesses and SMBs;
- ecommerce;
- multi-location operators;
- agencies/resellers;
- growth teams;
- enterprise;
- white-label partners.

Revenue models:
- direct subscription;
- managed audit;
- agency wholesale;
- white-label licensing;
- multi-site monitoring;
- enterprise measurement governance.

Pricing is deliberately **not current commercial truth yet**. The product enters
Buyer Acquisition as `MARKET_VALIDATE_TERMS_REQUIRED` and must receive a
separately governed pricing version before Empire can quote binding terms.

## Truth / authority rules

- missing tag != proven revenue loss;
- declared event != delivered conversion;
- Meta Pixel != verified CAPI;
- client-side code != server-side tagging proof;
- consent code != legal compliance;
- tag presence != working attribution;
- modeled opportunity != actual revenue;
- automatic tag mutation is false;
- measurement-platform writes are false;
- execution authority is none.
