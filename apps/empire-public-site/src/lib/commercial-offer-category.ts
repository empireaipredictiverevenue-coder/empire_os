/** Display-only category from the original, authoritative commercial offers GET. */
export function commercialOfferCategory(family: string): string {
  switch (family) {
    case "consultancy":
      return "Consultancy and advisory";
    case "digital_avatar":
      return "Digital Avatar — scoped deployment";
    case "intelligence_product":
      return "Intelligence product — scoped one-time delivery";
    default:
      // An unknown offer type must not masquerade as a Digital Avatar.
      return "Commercial proposal — scope requires review";
  }
}
