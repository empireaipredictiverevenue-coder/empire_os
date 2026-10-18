/**
 * First-party, unpriced Data Brokerage enquiry types.
 *
 * This is not a pricing catalog and must not be included on the public
 * commercial page until ASTRA + gateway owners approve and deploy both
 * premium discovery routes. No other site source needs modification.
 */
export const PREMIUM_DISCOVERY_ENDPOINT = "/v1/checkout/brokerage/premium-discovery" as const;

export const PREMIUM_DISCOVERY_CODES = [
  "brokerage_agency_discovery",
  "brokerage_enterprise_discovery",
] as const;

export type PremiumDiscoveryCode = (typeof PREMIUM_DISCOVERY_CODES)[number];

export type PremiumDiscoveryOffer = {
  product_code: PremiumDiscoveryCode;
  title: string;
  buyer_problem: string;
  price_state: "DISCUSS_CUSTOM_SCOPE";
  public_approved_price_available: false;
  request_type: "NONBINDING_FOUNDER_ENQUIRY";
  checkout_enabled: false;
};

export type PremiumDiscoveryCatalog = {
  schema_version: "empire.data_brokerage.gateway_candidate.v1";
  status: "UNPRICED_DISCOVERY_CHOICES_NONBINDING";
  count: 2;
  offers: PremiumDiscoveryOffer[];
  marketing_consent_included: false;
  customer_delivery_enabled: false;
  binding_terms_ready: false;
  payment_authorized: false;
};

export type PremiumDiscoveryReceipt = {
  decision: "commercial_enquiry_recorded";
  product_code: PremiumDiscoveryCode;
  reference: string;
  next_step: "FOUNDER_PRIVATE_SCOPE_REVIEW";
  binding_terms_ready: false;
  payment_action: false;
  revenue_recognized: false;
};

const codes = new Set<string>(PREMIUM_DISCOVERY_CODES);
const allowedKeys = new Set([
  "product_code", "title", "buyer_problem", "price_state",
  "public_approved_price_available", "request_type", "checkout_enabled",
]);

function object(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function parsePremiumDiscoveryCatalog(value: unknown): PremiumDiscoveryCatalog | null {
  if (!object(value) ||
      value.schema_version !== "empire.data_brokerage.gateway_candidate.v1" ||
      value.status !== "UNPRICED_DISCOVERY_CHOICES_NONBINDING" ||
      value.count !== 2 || !Array.isArray(value.offers) ||
      value.offers.length !== 2 ||
      value.marketing_consent_included !== false ||
      value.customer_delivery_enabled !== false ||
      value.binding_terms_ready !== false ||
      value.payment_authorized !== false) {
    return null;
  }
  const seen = new Set<string>();
  for (const raw of value.offers) {
    if (!object(raw) || !Object.keys(raw).every(key => allowedKeys.has(key)) ||
        typeof raw.product_code !== "string" ||
        !codes.has(raw.product_code) || seen.has(raw.product_code) ||
        typeof raw.title !== "string" || !raw.title ||
        raw.title.length > 120 ||
        typeof raw.buyer_problem !== "string" ||
        !raw.buyer_problem || raw.buyer_problem.length > 350 ||
        raw.price_state !== "DISCUSS_CUSTOM_SCOPE" ||
        raw.public_approved_price_available !== false ||
        raw.request_type !== "NONBINDING_FOUNDER_ENQUIRY" ||
        raw.checkout_enabled !== false) {
      return null;
    }
    seen.add(raw.product_code);
  }
  if (seen.size !== codes.size) return null;
  return value as PremiumDiscoveryCatalog;
}

export function parsePremiumDiscoveryReceipt(
  value: unknown, requested: PremiumDiscoveryCode,
): PremiumDiscoveryReceipt | null {
  if (!object(value) ||
      value.decision !== "commercial_enquiry_recorded" ||
      value.product_code !== requested ||
      typeof value.reference !== "string" ||
      !/^[a-f0-9]{20}$/.test(value.reference) ||
      value.next_step !== "FOUNDER_PRIVATE_SCOPE_REVIEW" ||
      value.binding_terms_ready !== false ||
      value.payment_action !== false ||
      value.revenue_recognized !== false) {
    return null;
  }
  return value as PremiumDiscoveryReceipt;
}
