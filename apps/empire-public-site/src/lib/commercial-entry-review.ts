/**
 * Browser-claimed, first-party entry page for the existing commercial enquiry.
 * Not a referrer, search-click proof, contact permission, or analytics event.
 * The EmpireOS intake owner repeats the same allowlist and stores the hint
 * only as unverified evidence with an actual consented enquiry.
 */
const INDUSTRY_ENTRY_SLUGS = ["roofing", "solar", "hvac", "property"] as const;
const REVIEWED_ENTRY_PATHS = new Set([
  "/", "/commercial", "/predictive-revenue",
  "/industries/roofing", "/industries/solar", "/industries/hvac",
  "/industries/property", "/insights/revenue-opportunity-assessment",
  "/aeo/general_contractor/NYC/", "/aeo/hvac/DFW/", "/aeo/roofing/DFW/",
]);

export function industryCommercialProposalHref(slug: string): string {
  if (!INDUSTRY_ENTRY_SLUGS.some(item => item === slug)) {
    return "/commercial#commercial-enquiry";
  }
  const path = "/industries/" + slug;
  return "/commercial?entry=" + encodeURIComponent(path) + "#commercial-enquiry";
}

/** Exact published, founder-approved AEO paths only. Never an attribution assertion. */
const AEO_MARKET_ROUTES = new Set([
  "/aeo/general_contractor/NYC/", "/aeo/hvac/DFW/", "/aeo/roofing/DFW/",
]);
export function aeoCommercialProposalHref(path: string): string {
  if (!AEO_MARKET_ROUTES.has(path)) return "/commercial#commercial-enquiry";
  return "/commercial?entry=" + encodeURIComponent(path) + "#commercial-enquiry";
}

export function claimedEntryForReview(search: string): string | undefined {
  // Never trust browser URL values as proof of search acquisition or buyers.
  if (typeof search !== "string" || search.length > 300) return undefined;
  const params = new URLSearchParams(search);
  if (params.getAll("entry").length !== 1) return undefined;
  const path = params.get("entry");
  return path && REVIEWED_ENTRY_PATHS.has(path) ? path : undefined;
}
