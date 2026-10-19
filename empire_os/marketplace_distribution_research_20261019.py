"""Empire AI — owned marketplace distribution research (no activation).

Distinguishes SELL_OWN_CALLS, EARN_AFFILIATE_COMMISSIONS,
SELL_SOFTWARE_API, SELL_OWN_DIGITAL_GOODS and SELL_LICENSED_B2B_DATA.
An external marketplace's public catalog, displayed payout or signup
page never authenticates a buyer's commitment, traffic rights,
merchant eligibility or available commercial inventory.

Untrusted source snapshots can only downgrade state, never admit buyers.
No requests, credentials, outreach, personal data, account creations,
database writes, code execution, listing publication or funds movement.
"""
from __future__ import annotations

from collections.abc import Mapping
from collections import Counter
from datetime import datetime, timezone
import re
from urllib.parse import urlsplit

SCHEMA = "empire.marketplace_distribution_research.v1"
SOURCE = "PUBLIC_FIRST_PARTY_PROVIDER_DOCS_REVIEWED_2026_10_19"
LANES = frozenset({
    "SELL_OWN_VERIFIED_INBOUND_CALLS", "EARN_AFFILIATE_COMMISSIONS",
    "SELL_SOFTWARE_OR_API", "SELL_LICENSED_B2B_DATA",
    "SELL_OWN_DIGITAL_DOWNLOADS", "RECRUIT_PRODUCT_AFFILIATES",
})
DOMAIN = re.compile(r"^(?:[a-z0-9-]+\.)+[a-z]{2,24}$")
MAX_REGISTRY = 3000
MAX_SWEEP = 100

# Only literal verified first-party provider/docs URL, not synthetic
# offer inventory. Confidence in the channel's *existence*, not sale.
CHANNELS = (
  ("awin-publisher", "Awin publisher", "awin.com", "EARN_AFFILIATE_COMMISSIONS",
   "https://www.awin.com/gb/getting-started", "CONTENT_AUDIENCE_AND_PROGRAM_APPROVAL",
   "Confirm UK publisher signup deposit and relevant US/UK service offers", 1),
  ("cj-publisher", "CJ Affiliate", "cj.com", "EARN_AFFILIATE_COMMISSIONS",
   "https://www.cj.com/en-gb/join", "ACTIVE_WEBSITE_REQUIRED",
   "CJ requires an active website; verify audience and specific brand PPL terms", 1),
  ("impact-publisher", "impact.com publisher", "impact.com", "EARN_AFFILIATE_COMMISSIONS",
   "https://impact.com/partners/", "MARKETPLACE_ADMISSION_AND_PROGRAM_APPROVAL",
   "Publisher joins marketplace then applies to an individually eligible programme", 1),
  ("partnerstack-publisher", "PartnerStack partner network", "partnerstack.com", "EARN_AFFILIATE_COMMISSIONS",
   "https://support.partnerstack.com/hc/en-us/articles/20574018677395-Joining-the-PartnerStack-Network",
   "B2B_SAAS_REFERRAL_ONLY", "Promote other B2B SaaS products; not a buyer for Empire AI consumer leads", 2),
  ("apify-actors", "Apify Store", "apify.com", "SELL_SOFTWARE_OR_API",
   "https://docs.apify.com/actors/publishing/monetize", "ACTOR_PRODUCT_AND_LICENSE_REVIEW",
   "Sell bounded licensed-source automation, not personal lead lists; benchmark platform runtime charges", 1),
  ("rapidapi-provider", "RapidAPI", "rapidapi.com", "SELL_SOFTWARE_OR_API",
   "https://docs.rapidapi.com/v2/docs/monetizing-your-api-on-rapidapicom",
   "SECURE_TENANT_API_AND_BILLING_REVIEW",
   "First make a documented, tenant-isolated, usage-metered and supported public API", 1),
  ("gumroad", "Gumroad", "gumroad.com", "SELL_OWN_DIGITAL_DOWNLOADS",
   "https://gumroad.com/help/article/66-gumroads-fees", "LICENSED_DOWNLOAD_AND_PAYOUT_REVIEW",
   "Sell original templates/research guides, not lead/contact files; validate payout terms", 2),
  ("lemon-squeezy", "Lemon Squeezy", "lemonsqueezy.com", "SELL_OWN_DIGITAL_DOWNLOADS",
   "https://docs.lemonsqueezy.com/help/getting-started/activate-your-store",
   "KYC_KYB_PRODUCT_AND_PAYOUT_REVIEW", "Merchant-of-record review for genuinely deliverable digital goods and SaaS", 2),
  ("aws-data-exchange", "AWS Data Exchange", "aws.amazon.com", "SELL_LICENSED_B2B_DATA",
   "https://docs.aws.amazon.com/data-exchange/latest/userguide/provider-getting-started.html",
   "PROVIDER_IDENTITY_TAX_BANK_AND_DATA_RIGHTS", "Requires qualified provider and rights-cleared non-sensitive products; UK onboarding verification", 3),
  ("aws-ai-marketplace", "AWS Marketplace AI agents", "aws.amazon.com", "SELL_SOFTWARE_OR_API",
   "https://docs.aws.amazon.com/marketplace/latest/userguide/listing-saas-ai-agents.html",
   "PRODUCTION_SAAS_AWS_INTEGRATION_KYC", "Enterprise-grade agent SaaS and fulfillment/billing integration required", 3),
  ("microsoft-marketplace", "Microsoft Marketplace SaaS", "microsoft.com", "SELL_SOFTWARE_OR_API",
   "https://learn.microsoft.com/en-us/partner-center/marketplace-offers/create-new-saas-offer",
   "PARTNER_CENTER_VERIFICATION_AND_SAAS_FULFILLMENT", "Cloud SaaS listing; not a lead reseller", 3),
  ("google-cloud-marketplace", "Google Cloud Marketplace", "google.com", "SELL_SOFTWARE_OR_API",
   "https://docs.cloud.google.com/marketplace/docs/partners/get-started",
   "INCORPORATED_VENDOR_AND_GCP_PRODUCTION_PRODUCT", "Published organization eligibility requires incorporation and GCP hosting; UK sole trader hold", 4),
  ("awin-advertiser", "Awin advertiser partnership programme", "awin.com",
   "RECRUIT_PRODUCT_AFFILIATES", "https://www.awin.com/gb/getting-started",
   "PAID_VENDOR_PROGRAM_NO_APPROVED_BUDGET",
   "To recruit affiliates for Empire SaaS, advertiser plan and proven checkout required; not a free publisher listing", 4),
  ("impact-advertiser", "impact.com brand partner programme", "impact.com",
   "RECRUIT_PRODUCT_AFFILIATES", "https://impact.com/",
   "PAID_VENDOR_PROGRAM_NO_APPROVED_BUDGET",
   "Brand-side marketplace programme requires product checkout, partner terms, approved budget and attribution", 4),
  ("partnerstack-vendor", "PartnerStack vendor recruitment", "partnerstack.com",
   "RECRUIT_PRODUCT_AFFILIATES", "https://partnerstack.com/",
   "PAID_VENDOR_PROGRAM_NO_APPROVED_BUDGET",
   "Vendor partnership programme pricing requires a quote; do not confuse free partner network with paid recruitment", 4),
  ("callscaler-existing", "CallScaler Marketplace", "callscaler.com", "SELL_OWN_VERIFIED_INBOUND_CALLS",
   "https://callscaler.com/marketplace/roofing/callscaler-network",
   "EXISTING_RESEARCH_NO_LIVE_TRAFFIC", "Previously reviewed by another owner; public offer is not Empire approved placement", 3),
  ("marketcall-existing", "Marketcall", "marketcall.com", "SELL_OWN_VERIFIED_INBOUND_CALLS",
   "https://www.marketcall.com/affiliates", "EXISTING_CONTACT_NO_DUPLICATE",
   "Already in legacy Empire research/contact history; no automatic new application", 4),
  ("aragon-existing", "Aragon Advertising", "aragon-advertising.com",
   "SELL_OWN_VERIFIED_INBOUND_CALLS", "https://aragon-advertising.com/join-network/",
   "EXISTING_CONTACT_NO_DUPLICATE", "Previous contact recorded; no duplicate outreach", 4),
  ("ringpartner-existing", "RingPartner", "ringpartner.com", "SELL_OWN_VERIFIED_INBOUND_CALLS",
   "https://ringpartner.com/", "OWNED_NETWORK_SWEEP", "Previously researched 19 October by buyer-network owner", 4),
  ("homeservpro-existing", "Home Serv Pro", "joinhomeservpro.com",
   "SELL_OWN_VERIFIED_INBOUND_CALLS", "https://joinhomeservpro.com/",
   "FOUNDER_PRIOR_APPLICATION_PENDING", "Founder already submitted form; await original response", 4),
)


def _domain(value: object) -> str:
    if not isinstance(value, str):
        return ""
    v = value.strip().lower().rstrip(".")
    if v.startswith("www."):
        v = v[4:]
    return v if DOMAIN.fullmatch(v) else ""


def _snapshots(registry: Mapping, sweep: Mapping) -> tuple[dict[str, list], set[str]]:
    if not isinstance(registry, Mapping) or not isinstance(sweep, Mapping):
        raise ValueError("missing_required_snapshots")
    if (registry.get("schema_version") != "empire.commercial_relationship_registry.v1"
        or registry.get("mode") != "OBSERVE"
        or registry.get("outbound_authorized") is not False
        or registry.get("outbound_sent") is not False
        or str(registry.get("execution_authority")).lower() != "none"):
        raise ValueError("untrusted_registry_contract")
    relationships = registry.get("relationships")
    if not isinstance(relationships, list) or len(relationships) > MAX_REGISTRY:
        raise ValueError("unbounded_registry")
    if (sweep.get("schema_version") != "empire.commercial.public_publisher_network_sweep.v1"
        or sweep.get("owner") != "existing_buyer_network_owner"
        or sweep.get("mode") != "READ_ONLY_RESEARCH"
        or sweep.get("outbound_sent") is not False
        or sweep.get("empiredb_writes") is not False):
        raise ValueError("untrusted_prior_network_sweep")
    entries = sweep.get("items")
    if not isinstance(entries, list) or len(entries) > MAX_SWEEP:
        raise ValueError("unbounded_network_sweep")
    known: dict[str,list] = {}
    for row in relationships:
        if not isinstance(row, Mapping):
            raise ValueError("malformed_registry_record")
        aliases = row.get("identity_domains")
        if not isinstance(aliases, list) or len(aliases)>40:
            raise ValueError("untrusted_identity_aliases")
        for candidate in aliases:
            domain = _domain(candidate)
            if domain:
                known.setdefault(domain, []).append(row)
    reviewed=set()
    for entry in entries:
        if not isinstance(entry, Mapping):
            raise ValueError("invalid_prior_network_row")
        domain = _domain(entry.get("domain"))
        if domain:
            reviewed.add(domain)
    for field in ("excluded_as_existing_empire_network_or_research",
                  "excluded_as_previously_contacted"):
        domains=sweep.get(field)
        if not isinstance(domains,list) or len(domains)>MAX_SWEEP:
            raise ValueError("untrusted_network_exclusion_list")
        reviewed.update(_domain(v) for v in domains if _domain(v))
    return known,reviewed


def review_marketplace_distribution(registry: Mapping, sweep: Mapping,
                                    *, at: datetime) -> dict:
    if at.tzinfo is None or at.utcoffset() is None:
        raise ValueError("review_timestamp_utc_required")
    known, reviewed = _snapshots(registry,sweep)
    rows=[]
    for slug, name, domain, lane, url, gate, action, priority in CHANNELS:
        if lane not in LANES or not _domain(domain) or urlsplit(url).scheme != "https":
            raise ValueError("catalogue_evidence_invalid")
        relationships=known.get(domain,[])
        contacted=any(bool(r.get("last_outbound_at") or r.get("last_inbound_at")
                           or r.get("gmail_thread_ids")) for r in relationships)
        suppressed=any(r.get("do_not_pursue") is True or bool(r.get("bounced_addresses"))
                       for r in relationships)
        # Public official program URLs support the channel *route*, NOT
        # admission, accepted traffic or live inventory/offer contracts.
        if suppressed:
            state="SUPPRESSED_OR_BOUNCE_HOLD"
        elif contacted or gate == "EXISTING_CONTACT_NO_DUPLICATE":
            state="EXISTING_RELATIONSHIP_HOLD"
        elif domain in reviewed or gate in ("OWNED_NETWORK_SWEEP", "FOUNDER_PRIOR_APPLICATION_PENDING",
                                             "EXISTING_RESEARCH_NO_LIVE_TRAFFIC"):
            state="OTHER_OWNER_RESEARCH_OR_APPLICATION_HOLD"
        elif gate == "PAID_VENDOR_PROGRAM_NO_APPROVED_BUDGET":
            state="PAID_VENDOR_PROGRAM_BUDGET_HOLD"
        elif gate in ("INCORPORATED_VENDOR_AND_GCP_PRODUCTION_PRODUCT",
                      "PROVIDER_IDENTITY_TAX_BANK_AND_DATA_RIGHTS",
                      "PRODUCTION_SAAS_AWS_INTEGRATION_KYC",
                      "PARTNER_CENTER_VERIFICATION_AND_SAAS_FULFILLMENT"):
            state="LONG_TERM_COMPLIANCE_ELIGIBILITY"
        else:
            state="NEW_CHANNEL_ELIGIBILITY_REVIEW"
        rows.append({
            "id":slug,"name":name,"domain":domain,"lane":lane,
            "official_source_url":url,
            "state":state,"priority_lower_is_earlier":priority,
            "first_gate":gate,"next_research_action":action,
            "previously_contacted_in_canonical_relationships":contacted,
            "prior_network_sweep_overlap":domain in reviewed,
            "commercial_buyer_verified":False,
            "existing_empire_account_verified":False,
            "seller_onboarding_verified":False,
            "active_approved_offer_for_empire_verified":False,
            "sellable_inventory_verified":False,
            "first_payer_funded_capacity_verified":False,
            "application_submitted":False,
            "publisher_recruited":False,
            "product_listed":False,
            "traffic_or_payments_activated":False,
        })
    rows.sort(key=lambda r:(r["priority_lower_is_earlier"],r["name"]))
    counts=Counter(row["state"] for row in rows)
    return {
      "schema_version":SCHEMA,
      "reviewed_at":at.astimezone(timezone.utc).isoformat(),
      "mode":"READ_ONLY_MARKETPLACE_DISCOVERY",
      "existing_network_sweep_owner":sweep.get("owner"),
      "source":SOURCE,
      "marketplace_routes_reviewed":len(rows),
      "new_channel_eligibility_reviews":counts["NEW_CHANNEL_ELIGIBILITY_REVIEW"],
      "existing_relationship_holds":counts["EXISTING_RELATIONSHIP_HOLD"],
      "other_owner_overlap_holds":counts["OTHER_OWNER_RESEARCH_OR_APPLICATION_HOLD"],
      "long_term_eligibility_holds":counts["LONG_TERM_COMPLIANCE_ELIGIBILITY"],
      "paid_vendor_budget_holds":counts["PAID_VENDOR_PROGRAM_BUDGET_HOLD"],
      "suppression_holds":counts["SUPPRESSED_OR_BOUNCE_HOLD"],
      "confirmed_paying_marketplaces":0,"new_registered_publishers":0,
      "actual_product_listings_published":0,"applications_submitted":0,
      "saleable_lead_inventory_verified":False,
      "unverified_marketplace_payouts_ignored":True,
      "traffic_rights_and_source_licenses_required":True,
      "canonical_suppression_before_outreach_required":True,
      "no_contact_history_cleared_by_missing_domain":True,
      "primary_buyer_scout_modified":False,
      "marketplace_items":rows,
      "outbound_authorized":False,"canonical_empiredb_writes":False,
      "execution_authority":"none",
    }
