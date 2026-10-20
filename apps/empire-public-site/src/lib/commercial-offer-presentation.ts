/** Public, non-binding offer catalogue presentation. No backend authority here. */
export type CommercialOffer = {
  product_code: string;
  name: string;
  offer_family: string;
  currency: string;
  approved_price_cents: number;
  price_interval: string;
  implementation_fee_cents?: number;
};

export const COMMERCIAL_OFFER_FILTERS = [
  { value: "all", label: "All solutions" },
  { value: "consultancy", label: "Consultancy" },
  { value: "digital_avatar", label: "Digital Avatars" },
  { value: "intelligence_product", label: "Intelligence Products" },
] as const;

export type CommercialOfferFilter = (typeof COMMERCIAL_OFFER_FILTERS)[number]["value"];

export function filterCommercialOffers(
  offers: readonly CommercialOffer[],
  family: CommercialOfferFilter,
): CommercialOffer[] {
  return offers.filter(offer => family === "all" || offer.offer_family === family);
}

export function commercialOfferFamilyLabel(offer: CommercialOffer): string {
  switch (offer.offer_family) {
    case "consultancy": return "Consultancy and advisory";
    case "digital_avatar": return "Digital Avatar — scoped deployment";
    case "intelligence_product": return "Intelligence product — scoped availability";
    default: return "Solution scope to be confirmed";
  }
}

function money(offer: CommercialOffer, cents: number): string {
  const prefix = offer.currency === "GBP" ? "£" :
    offer.currency === "USD" ? "$" : offer.currency + " ";
  return prefix + (cents / 100).toLocaleString("en-GB", { minimumFractionDigits: cents % 100 ? 2 : 0, maximumFractionDigits: 2 });
}

export function commercialOfferPrice(offer: CommercialOffer): string {
  return money(offer, offer.approved_price_cents) +
    (offer.price_interval === "monthly" ? "/month" : "");
}

export function commercialOfferSetupFee(offer: CommercialOffer): string {
  return typeof offer.implementation_fee_cents === "number" && offer.implementation_fee_cents > 0
    ? " · Setup " + money(offer, offer.implementation_fee_cents)
    : "";
}
