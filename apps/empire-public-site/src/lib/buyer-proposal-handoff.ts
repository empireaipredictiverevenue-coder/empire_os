/** Nonbinding first-party buyer proposal handoff. No submission or storage. */
export const INTELLIGENCE_PROPOSAL_CODES = [
  "competitor_search_gap",
  "search_opportunity_map",
  "technical_search_audit",
  "solar_opportunity_map_us",
] as const;

const CODE_PATTERN = /^[a-z][a-z0-9_]{2,63}$/;

export function approvedProposalHref(code: string | null): string {
  if (!code || !INTELLIGENCE_PROPOSAL_CODES.some(item => item === code)) {
    return "/commercial#commercial-enquiry";
  }
  return "/commercial?product=" + encodeURIComponent(code) + "#commercial-enquiry";
}

export type ProposalOffer = { product_code: string };

export function selectApprovedProposalOffer(
  requested: string | null,
  offers: readonly ProposalOffer[],
): { code: string; rejected: boolean } {
  if (requested === null) {
    const first = offers[0]?.product_code;
    return {
      code: typeof first === "string" && CODE_PATTERN.test(first) ? first : "",
      rejected: false,
    };
  }
  // A browser URL is always untrusted. The backend's current approved
  // first-party offers GET is the only authority to select a product.
  if (!CODE_PATTERN.test(requested)) {
    return { code: "", rejected: true };
  }
  const matched = offers.find(offer => offer?.product_code === requested);
  return { code: matched ? matched.product_code : "", rejected: !matched };
}
