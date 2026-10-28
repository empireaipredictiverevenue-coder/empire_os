// API fields ending in _cents use hundredths, not arbitrary minor units.
export function currencyOf(value: unknown): unknown {
  return typeof value === "object" && value !== null && "currency" in value
    ? value.currency : undefined;
}

export function moneyCents(amount: unknown, currency: unknown): string {
  if (typeof amount !== "number" || !Number.isSafeInteger(amount)) return "UNKNOWN";
  if (typeof currency !== "string" || !Intl.supportedValuesOf("currency").includes(currency)) return "UNKNOWN";
  const formatter = new Intl.NumberFormat("en-GB", { style: "currency", currency, currencyDisplay: "code" });
  // Never interpret yen or three-decimal currencies as hundredths.
  if (formatter.resolvedOptions().maximumFractionDigits !== 2) return "UNKNOWN";
  return formatter.format(amount / 100);
}
