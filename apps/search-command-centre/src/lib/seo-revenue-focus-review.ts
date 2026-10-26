/**
 * Original SEO Founder evidence-only presentation. Validates only private
 * original-owner read-only lifecycle receipts; never infers buyer origins.
 */
export type SeoOwnerFocus = {
  status: string;
  next_existing_owner_action: string;
  google_unknown_exact_buyer_entry_urls: string[];
  sitewide_canonical_sales_count: number | null;
  count_source_verified: boolean;
  seo_attributed_buyer_count: null;
  earned_revenue_verified: false;
  new_publication_authorized: false;
  google_indexing_requests_submitted: 0;
};

export type AeoLinkCanary = {
  status: "THREE_AEO_TO_COMMERCIAL_SOURCE_LINKS_GET_VERIFIED" | "HELD";
  live_aeo_links_verified: number;
  commercial_compiled_claim_support_verified: boolean;
  submitted_enquiries_verified: false;
  outbound_sent: false;
  database_writes: false;
};

export function safeSeoFocus(
  value: unknown, context: { observed_at?: string; now?: Date } = {},
): { focus: SeoOwnerFocus | null; reason: string | null; aged: boolean } {
  const latest = Date.parse(context.observed_at ?? "");
  const now = (context.now ?? new Date()).getTime();
  const aged = !Number.isFinite(latest) || latest > now + 5 * 60_000 ||
                now - latest > 3 * 60 * 60_000;
  if (typeof value !== "object" || !value || Array.isArray(value)) {
    return { focus: null, reason: "FOCUS_NOT_IN_SAVED_ORIGINAL_OWNER_RECEIPT", aged };
  }
  const v = value as Record<string, unknown>;
  const permitted = new Set([
    "https://empire-ai.co.uk/commercial",
    "https://empire-ai.co.uk/industries/solar",
  ]);
  const acceptableStatuses = new Set([
    "GROW_DISCOVERY_FOR_PUBLISHED_BUYER_ENTRY",
    "EXISTING_CANONICAL_ENQUIRY_REQUIRES_CRM_REVIEW",
    "CANONICAL_SALES_SOURCE_UNVERIFIED",
    "MEASURE_GSC_VISITS_AND_CONSENTED_BUYER_RESPONSE",
  ]);
  if (!acceptableStatuses.has(String(v.status)) ||
      typeof v.next_existing_owner_action !== "string" ||
      v.next_existing_owner_action.length > 200 ||
      !/^[A-Z0-9_;]+$/.test(v.next_existing_owner_action) ||
      !Array.isArray(v.google_unknown_exact_buyer_entry_urls) ||
      v.google_unknown_exact_buyer_entry_urls.length > 2 ||
      new Set(v.google_unknown_exact_buyer_entry_urls).size !==
        v.google_unknown_exact_buyer_entry_urls.length ||
      v.google_unknown_exact_buyer_entry_urls.some((u) =>
        typeof u !== "string" || !permitted.has(u)) ||
      typeof v.count_source_verified !== "boolean" ||
      (v.sitewide_canonical_sales_count !== null &&
        (!Number.isSafeInteger(v.sitewide_canonical_sales_count) ||
          (v.sitewide_canonical_sales_count as number) < 0)) ||
      (v.count_source_verified === false && v.sitewide_canonical_sales_count !== null) ||
      (v.count_source_verified === true && v.sitewide_canonical_sales_count === null) ||
      v.seo_attributed_buyer_count !== null ||
      v.earned_revenue_verified !== false ||
      v.new_publication_authorized !== false ||
      v.google_indexing_requests_submitted !== 0) {
    return { focus: null, reason: "UNTRUSTED_OR_CONTRADICTORY_REVENUE_FOCUS", aged };
  }
  return { focus: v as SeoOwnerFocus, reason: null, aged };
}

export function safeAeoCanary(value: unknown): AeoLinkCanary | null {
  if (typeof value !== "object" || !value || Array.isArray(value)) return null;
  const v = value as Record<string, unknown>;
  if (!["THREE_AEO_TO_COMMERCIAL_SOURCE_LINKS_GET_VERIFIED", "HELD"].includes(
      String(v.status)) ||
      !Number.isInteger(v.live_aeo_links_verified) ||
      (v.live_aeo_links_verified as number) < 0 ||
      (v.live_aeo_links_verified as number) > 3 ||
      typeof v.commercial_compiled_claim_support_verified !== "boolean" ||
      v.submitted_enquiries_verified !== false ||
      v.outbound_sent !== false || v.database_writes !== false) return null;
  if (v.status === "THREE_AEO_TO_COMMERCIAL_SOURCE_LINKS_GET_VERIFIED" &&
      (v.live_aeo_links_verified !== 3 ||
       v.commercial_compiled_claim_support_verified !== true)) return null;
  return v as AeoLinkCanary;
}
